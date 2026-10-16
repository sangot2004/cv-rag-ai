from threading import Lock

from langgraph.types import Command

from src.auth.service import require_user, resolve_department
from src.chat.checkpoints import get_checkpointer
from src.chat.conversation_store import require_conversation
from src.chat.errors import DependencyUnavailable
from src.llm.key_manager import get_key_manager, is_quota_error
from src.llm.prompt_store import get_prompt_commit
from src.retrieval.access_scope import department_scope

_graph_lock = Lock()
_graph = None
_graph_key = None


def _get_graph():
    global _graph, _graph_key
    from src.agent.agent_executor import build_agent_executor
    user = require_user()
    try:
        current_key = get_key_manager().get_current_key()
        prompt_commit = get_prompt_commit("cv-rag-agent-system")
    except ValueError as exc:
        raise DependencyUnavailable("Agent configuration is unavailable") from exc
    saver = get_checkpointer()
    identity = (current_key, user.role, prompt_commit, id(saver))
    with _graph_lock:
        if _graph is None or _graph_key != identity:
            _graph = build_agent_executor(current_key, checkpointer=saver, role=user.role)
            _graph_key = identity
        return _graph


def _invoke(thread_id, graph_input, department_id=None):
    require_conversation(thread_id)
    department_id = resolve_department(department_id)
    try:
        graph = _get_graph()
        with department_scope(department_id):
            return graph.invoke(graph_input, config={"configurable": {"thread_id": thread_id}})
    except Exception as exc:
        # Do not replay the entire input: tools may have already completed.
        if is_quota_error(exc):
            get_key_manager().mark_exhausted()
        raise


def _invoke_ask(question, thread_id, department_id=None):
    return _invoke(thread_id, {"messages": [{"role": "user", "content": question}]}, department_id)


def _invoke_resume(thread_id, confirmation_id, confirmed, edited_criteria=None, department_id=None):
    value = {"confirmed": confirmed, "edited_criteria": edited_criteria}
    return _invoke(thread_id, Command(resume={confirmation_id: value}), department_id)


def get_conversation_messages(thread_id):
    from src.chat.service import history
    return history(thread_id)["messages"]


def has_pending_confirmation(thread_id):
    from src.chat.service import history
    pending = history(thread_id)["pending_confirmations"]
    return {"type": pending[0]["type"], "confirmation_id": pending[0]["confirmation_id"],
            **pending[0]["criteria"]} if pending else None


def _legacy_response(result):
    if result["type"] == "confirmation_required":
        pending = result["pending_confirmations"][0]
        return {**result, "payload": {"type": pending["type"],
                                     "confirmation_id": pending["confirmation_id"], **pending["criteria"]}}
    message = result.get("message")
    return {**result, "type": "answer", "content": message["content"] if message else "Đã hủy yêu cầu."}


def ask(question, thread_id, department_id=None):
    from src.chat.service import send_message
    return _legacy_response(send_message(thread_id, question, department_id=department_id))


def resume(thread_id, confirmed, edited_criteria=None, department_id=None, confirmation_id=None):
    from src.chat.service import resume_message
    # Streamlit displays the first pending form; select it under the lock.
    return _legacy_response(resume_message(thread_id, confirmation_id, confirmed, edited_criteria,
                                           department_id=department_id))
