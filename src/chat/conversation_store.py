import logging
import uuid
from datetime import datetime, timezone

from src.auth.service import require_user
from src.db.models import ChatConversation, ChatFeedback
from src.db.session import SessionLocal
from src.auth.errors import ConversationNotFound
from src.chat.concurrency import conversation_lock
from src.chat.errors import CleanupPending

logger = logging.getLogger(__name__)

TITLE_MAX_LENGTH = 40


def require_conversation(thread_id, session=None, *, include_deleted=False):
    user = require_user()
    if session is None:
        with SessionLocal() as db:
            return require_conversation(thread_id, db, include_deleted=include_deleted)
    conv = session.get(ChatConversation, thread_id)
    if conv is None or (conv.deleted_at is not None and not include_deleted) or conv.owner_user_id != user.user_id:
        raise ConversationNotFound("Không tìm thấy hội thoại hoặc bạn không có quyền truy cập.")
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
                "created_at": c.created_at,
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
    # Only DELETE may revisit an owned tombstone to retry physical cleanup.
    require_conversation(thread_id, include_deleted=True)
    with conversation_lock(thread_id):
        with SessionLocal() as session:
            conv = require_conversation(thread_id, session, include_deleted=True)
            if conv.deleted_at is None:
                conv.deleted_at = datetime.now(timezone.utc)
            session.query(ChatFeedback).filter_by(thread_id=thread_id).delete()
            session.commit()

        from src.chat.checkpoints import delete_checkpoints
        try:
            delete_checkpoints(thread_id)
        except Exception as exc:
            raise CleanupPending("Hội thoại đã ẩn; cần thử xóa lại để dọn checkpoint.") from exc


def conversation_metadata(thread_id: str) -> dict:
    conv = require_conversation(thread_id)
    return {key: getattr(conv, key) for key in ("thread_id", "title", "created_at", "updated_at")}
