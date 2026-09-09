import logging

from src.db.models import ChatFeedback
from src.db.session import SessionLocal

logger = logging.getLogger(__name__)


def save_feedback(thread_id: str, question: str, answer: str, feedback: str) -> None:
    """Lưu phản hồi của người dùng về câu trả lời của AI."""
    if feedback not in ("up", "down"):
        raise ValueError(f"feedback phải là 'up' hoặc 'down', nhưng nhận được: {feedback!r}")

    with SessionLocal() as session:
        session.add(
            ChatFeedback(thread_id=thread_id, question=question, answer=answer, feedback=feedback)
        )
        session.commit()
    logger.info("Lưu feedback=%s cho thread_id=%s", feedback, thread_id)


def get_negative_feedback_examples(limit: int = 50) -> list[dict]:
    """Lấy các câu hỏi bị phản hồi tiêu cực (feedback='down') để 
    phân tích hoặc huấn luyện lại."""
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
