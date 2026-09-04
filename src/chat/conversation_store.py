import logging
import uuid

from src.db.models import ChatConversation
from src.db.session import SessionLocal

logger = logging.getLogger(__name__)

TITLE_MAX_LENGTH = 40


def create_conversation() -> str:
    thread_id = str(uuid.uuid4())
    with SessionLocal() as session:
        session.add(ChatConversation(thread_id=thread_id))
        session.commit()
    logger.info("Tạo conversation mới: %s", thread_id)
    return thread_id


def list_conversations(limit: int = 50) -> list[dict]:
    """Danh sách hội thoại"""
    with SessionLocal() as session:
        conversations = (
            session.query(ChatConversation)
            .order_by(ChatConversation.updated_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "thread_id": c.thread_id,
                "title": c.title,
                "updated_at": c.updated_at,
            }
            for c in conversations
        ]


def touch_conversation(thread_id: str, first_message: str | None = None) -> None:
    with SessionLocal() as session:
        conv = session.get(ChatConversation, thread_id)
        if conv is None:
            conv = ChatConversation(thread_id=thread_id)
            session.add(conv)

        if first_message and conv.title == "Cuộc trò chuyện mới":
            title = first_message.strip()[:TITLE_MAX_LENGTH]
            if len(first_message.strip()) > TITLE_MAX_LENGTH:
                title += "..."
            conv.title = title

        session.commit()


def delete_conversation(thread_id: str) -> None:
    with SessionLocal() as session:
        conv = session.get(ChatConversation, thread_id)
        if conv:
            session.delete(conv)
            session.commit()
            logger.info("Đã xoá conversation: %s", thread_id)
