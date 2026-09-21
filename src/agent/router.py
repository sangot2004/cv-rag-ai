import logging

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from src.agent.agent_executor import build_agent_executor
from src.chat.conversation_store import touch_conversation
from src.llm.key_manager import get_key_manager, is_quota_error
from src.retrieval.access_scope import department_scope

logger = logging.getLogger(__name__)

_checkpointer_cm = SqliteSaver.from_conn_string("chat_history.db")
_checkpointer = _checkpointer_cm.__enter__()

_graph = None
_graph_key: str | None = None


def _get_graph():
    """Lazy build — tránh khởi tạo LLM client lúc import module."""
    global _graph, _graph_key
    current_key = get_key_manager().get_current_key()
    if _graph is None or _graph_key != current_key:
        _graph = build_agent_executor(current_key, checkpointer=_checkpointer)
        _graph_key = current_key
    return _graph


def get_conversation_messages(thread_id: str) -> list[dict]:
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = _get_graph().get_state(config)
    except Exception:
        logger.exception("Không đọc được state cho thread_id=%s", thread_id)
        return []

    if not state or not state.values.get("messages"):
        return []

    messages = []
    for msg in state.values["messages"]:
        msg_type = getattr(msg, "type", None)
        if msg_type == "human":
            messages.append({"role": "user", "content": msg.content})
        elif msg_type == "ai" and msg.content:
            messages.append({"role": "assistant", "content": msg.content})

    return messages


def has_pending_confirmation(thread_id: str) -> dict | None:
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = _get_graph().get_state(config)
    except Exception:
        return None

    if state and state.tasks:
        for task in state.tasks:
            if task.interrupts:
                return task.interrupts[0].value
    return None


def _build_response(result: dict) -> dict:
    if "__interrupt__" in result:
        interrupt_obj = result["__interrupt__"][0]
        return {"type": "confirmation_required", "payload": interrupt_obj.value}

    answer = result["messages"][-1].content
    return {"type": "answer", "content": answer}


def ask(question: str, thread_id: str = "default", department_id: str | None = None) -> dict:
    logger.info("Agent nhận câu hỏi (thread_id=%s, department_id=%s): %r", thread_id, department_id, question)

    manager = get_key_manager()
    config = {"configurable": {"thread_id": thread_id}}
    last_error: Exception | None = None

    for attempt in range(manager.num_keys):
        try:
            graph = _get_graph()
            with department_scope(department_id):
                result = graph.invoke(
                    {"messages": [{"role": "user", "content": question}]}, config=config
                )
            response = _build_response(result)

            if response["type"] == "answer":
                touch_conversation(thread_id, first_message=question)

            logger.info("Agent response type=%s", response["type"])
            return response
        except Exception as e:
            last_error = e
            if is_quota_error(e) and attempt < manager.num_keys - 1:
                manager.mark_exhausted()
                continue
            raise
    raise last_error


def resume(
        thread_id: str,
        confirmed: bool,
        edited_criteria: dict | None = None,
        department_id: str | None = None,
) -> dict:
    manager = get_key_manager()
    config = {"configurable": {"thread_id": thread_id}}
    resume_value = {"confirmed": confirmed, "edited_criteria": edited_criteria}
    last_error: Exception | None = None

    for attempt in range(manager.num_keys):
        try:
            graph = _get_graph()
            with department_scope(department_id):
                result = graph.invoke(Command(resume=resume_value), config=config)
            response = _build_response(result)

            if response["type"] == "answer":
                touch_conversation(thread_id)

            logger.info("Resume response type=%s", response["type"])
            return response
        except Exception as e:
            last_error = e
            if is_quota_error(e) and attempt < manager.num_keys - 1:
                manager.mark_exhausted()
                continue
            raise

    raise last_error
