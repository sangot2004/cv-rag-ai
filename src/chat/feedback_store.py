import json
import logging

from src.db.models import ChatFeedback
from src.db.session import SessionLocal
from src.auth.service import admin_only
from src.chat.conversation_store import require_conversation

logger = logging.getLogger(__name__)


def _ensure_string(data) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        # Nếu là mảng dict của Gemini, cố gắng rút phần 'text' ra
        texts = []
        for item in data:
            if isinstance(item, dict) and "text" in item:
                texts.append(str(item["text"]))
            else:
                texts.append(str(item))
        return "\n".join(texts)
    if isinstance(data, dict):
        return json.dumps(data, ensure_ascii=False)

    return str(data)


def save_feedback(thread_id: str, question: str, answer: str, feedback: str) -> None:
    """Lưu phản hồi của người dùng về câu trả lời của AI."""
    require_conversation(thread_id)
    if feedback not in ("up", "down"):
        raise ValueError(f"feedback phải là 'up' hoặc 'down', nhưng nhận được: {feedback!r}")

    safe_question = _ensure_string(question)
    safe_answer = _ensure_string(answer)

    with SessionLocal() as session:
        session.add(
            ChatFeedback(
                thread_id=thread_id,
                question=safe_question,
                answer=safe_answer,
                feedback=feedback
            )
        )
        session.commit()
    logger.info("Lưu feedback=%s cho thread_id=%s", feedback, thread_id)


@admin_only
def get_negative_feedback_examples(limit: int = 50) -> list[dict]:
    with SessionLocal() as session:
        rows = (
            session.query(ChatFeedback)
            .filter(ChatFeedback.feedback == "down")
            .order_by(ChatFeedback.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {"question": r.question, "answer": r.answer, "created_at": str(r.created_at)}
            for r in rows
        ]
