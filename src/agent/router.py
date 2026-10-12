import logging
from threading import Lock

from src.chat.checkpoints import get_checkpointer
from src.auth.service import require_user, resolve_department
from langgraph.types import Command

from src.ops.telemetry import monitored
from src.agent.agent_executor import build_agent_executor
from src.chat.conversation_store import touch_conversation, require_conversation
from src.llm.key_manager import get_key_manager, is_quota_error
from src.llm.prompt_store import get_prompt_commit
from src.retrieval.access_scope import department_scope

logger = logging.getLogger(__name__)

_graph_lock = Lock()
_graph = None
_graph_key: tuple[str, str, str] | None = None


def _get_graph():
    """Lazy build — tránh khởi tạo LLM client lúc import module."""
    global _graph, _graph_key
    user = require_user()
    current_key = get_key_manager().get_current_key()
    graph_identity = (current_key, user.role, get_prompt_commit("cv-rag-agent-system"))

    with _graph_lock:
        if _graph is None or _graph_key != graph_identity:
            _graph = build_agent_executor(current_key, checkpointer=get_checkpointer(), role=user.role)
            _graph_key = graph_identity
        return _graph


def get_conversation_messages(thread_id: str) -> list[dict]:
    require_conversation(thread_id)
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
    require_conversation(thread_id)
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


@monitored('agent_chat', ref='thread_id')
def ask(question: str, thread_id: str, department_id: str | None = None) -> dict:
    require_conversation(thread_id)
    department_id = resolve_department(department_id)
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


@monitored('agent_resume', ref='thread_id')
def resume(
        thread_id: str,
        confirmed: bool,
        edited_criteria: dict | None = None,
        department_id: str | None = None,
) -> dict:
    require_conversation(thread_id)
    department_id = resolve_department(department_id)
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
