import logging
import uuid
from datetime import datetime, timezone

from src.auth.service import AccessDenied, require_user
from src.db.models import ChatConversation, ChatFeedback
from src.db.session import SessionLocal

logger = logging.getLogger(__name__)

TITLE_MAX_LENGTH = 40


def require_conversation(thread_id, session=None):
    user = require_user()
    if session is None:
        with SessionLocal() as db:
            return require_conversation(thread_id, db)
    conv = session.get(ChatConversation, thread_id)
    if conv is None or conv.deleted_at is not None or conv.owner_user_id != user.user_id:
        raise AccessDenied("Không tìm thấy hội thoại hoặc bạn không có quyền truy cập.")
    return conv


def create_conversation() -> str:
    user = require_user()
    thread_id = str(uuid.uuid4())
    with SessionLocal() as session:
        session.add(ChatConversation(thread_id=thread_id, owner_user_id=user.user_id))
        session.commit()
    logger.info("Tạo conversation mới: %s", thread_id)
    return thread_id


def list_conversations(limit: int = 50) -> list[dict]:
    user = require_user()
    with SessionLocal() as session:
        rows = (session.query(ChatConversation)
                .filter(ChatConversation.owner_user_id == user.user_id,
                        ChatConversation.deleted_at.is_(None))
                .order_by(ChatConversation.updated_at.desc()).limit(limit).all())
        return [
            {
                "thread_id": c.thread_id,
                "title": c.title,
                "updated_at": c.updated_at
            }
            for c in rows
        ]


def touch_conversation(thread_id: str, first_message: str | None = None) -> None:
    with SessionLocal() as session:
        conv = require_conversation(thread_id, session)
        if first_message and conv.title == "Cuộc trò chuyện mới":
            text = first_message.strip()
            conv.title = text[:TITLE_MAX_LENGTH] + ("..." if len(text) > TITLE_MAX_LENGTH else "")
        conv.updated_at = datetime.now(timezone.utc)
        session.commit()


def delete_conversation(thread_id: str) -> None:
    with SessionLocal() as session:
        conv = require_conversation(thread_id, session)
        conv.deleted_at = datetime.now(timezone.utc)
        session.query(ChatFeedback).filter_by(thread_id=thread_id).delete()
        session.commit()

    from src.chat.checkpoints import delete_checkpoints

    delete_checkpoints(thread_id)
