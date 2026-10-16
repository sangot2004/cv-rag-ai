"""Shared chat orchestration; no HTTP or Streamlit dependencies."""
from src.chat import checkpoints
from src.chat.concurrency import conversation_lock, is_running
from src.chat.conversation_store import require_conversation, touch_conversation
from src.chat.errors import ChatConflict, MessageNotFound
from src.chat.message_adapter import pending_confirmations, visible_messages
from src.ops.telemetry import monitored
from src.chat.criteria import CriteriaEdits
from src.auth.service import resolve_department


def history(thread_id: str) -> dict:
    require_conversation(thread_id)
    state = checkpoints.read_state(thread_id)
    pending = pending_confirmations(state)
    require_conversation(thread_id)
    status = "idle"
    if is_running(thread_id):
        status = "running"
    elif any(task.error for task in state.tasks):
        status = "failed"
    elif pending:
        status = "awaiting_confirmation"
    elif state.next:
        status = "interrupted"
    return {
        "thread_id": thread_id,
        "messages": visible_messages(thread_id, state.values.get("messages", [])),
        "pending_confirmations": pending,
        "execution_status": status,
    }


def _result(thread_id, *, cancelled=False):
    current = history(thread_id)
    if current["pending_confirmations"]:
        return {"type": "confirmation_required", "thread_id": thread_id,
                "pending_confirmations": current["pending_confirmations"]}
    messages = current["messages"]
    if messages and messages[-1]["role"] == "assistant":
        return {"type": "answer", "thread_id": thread_id, "message": messages[-1]}
    if cancelled:
        return {"type": "cancelled", "thread_id": thread_id, "message": None}
    raise RuntimeError("Agent finished without a visible answer")


@monitored("agent_chat", ref="thread_id")
def send_message(thread_id: str, question: str, *, department_id=None) -> dict:
    from src.agent import router
    require_conversation(thread_id)
    department_id = resolve_department(department_id)
    with conversation_lock(thread_id, execution=True):
        current = history(thread_id)
        if current["pending_confirmations"]:
            raise ChatConflict("CONFIRMATION_PENDING", "Hãy xác nhận hoặc hủy tiêu chí trước khi hỏi tiếp.")
        state = checkpoints.read_state(thread_id)
        if state.next:
            raise ChatConflict("EXECUTION_INCOMPLETE", "Lượt trước chưa hoàn tất. Hãy tạo hội thoại mới.")
        touch_conversation(thread_id, first_message=question)
        router._invoke_ask(question, thread_id, department_id)
        return _result(thread_id)


@monitored("agent_resume", ref="thread_id")
def resume_message(thread_id: str, confirmation_id: str | None, confirmed: bool,
                   edited_criteria: dict | None = None, *, department_id=None) -> dict:
    from src.agent import router
    require_conversation(thread_id)
    department_id = resolve_department(department_id)
    if edited_criteria is not None:
        edited_criteria = CriteriaEdits.model_validate(edited_criteria).model_dump(exclude_unset=True)
    with conversation_lock(thread_id, execution=True):
        pending = history(thread_id)["pending_confirmations"]
        if not pending:
            raise ChatConflict("NO_PENDING_CONFIRMATION", "Hội thoại không có yêu cầu xác nhận.")
        confirmation_id = confirmation_id or pending[0]["confirmation_id"]
        if confirmation_id not in {item["confirmation_id"] for item in pending}:
            raise ChatConflict("STALE_CONFIRMATION", "Yêu cầu xác nhận đã thay đổi. Hãy tải lại hội thoại.")
        router._invoke_resume(thread_id, confirmation_id, confirmed, edited_criteria, department_id)
        touch_conversation(thread_id)
        return _result(thread_id, cancelled=not confirmed)


def submit_feedback(thread_id, message_id, feedback):
    from src.chat.feedback_store import save_feedback
    require_conversation(thread_id)
    with conversation_lock(thread_id):
        messages = history(thread_id)["messages"]
        question = None
        for message in messages:
            if message["role"] == "user":
                question = message["content"]
            elif message["id"] == message_id and question is not None:
                save_feedback(thread_id, question, message["content"], feedback)
                return {"message_id": message_id, "feedback": feedback}
        raise MessageNotFound("Không tìm thấy câu trả lời trong hội thoại.")
