import logging

from src.db.models import Candidate, SentEmail
from src.db.session import SessionLocal
from src.ingestion.email_intake.gmail_client import GmailClient

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    pass


def has_already_sent(candidate_id: str) -> bool:
    with SessionLocal() as session:
        existing = (
            session.query(SentEmail.id).filter(SentEmail.candidate_id ==
                                               candidate_id, SentEmail.status == "success").first()
        )
        return existing is not None


def send_interview_invitation(candidate_id: str, subject: str, body: str, batch_id: str | None = None) -> dict:
    with SessionLocal() as session:
        candidate = session.get(Candidate, candidate_id)
        if candidate is None:
            return {"success": False, "message_id": None, "error": f"candidate_id={candidate_id} không tồn tại"}
        if not candidate.email:
            return {"success": False, "message_id": None, "error": "Candidate không có email liên hệ"}

        recipient = candidate.email

    try:
        gmail = GmailClient()
        message_id = gmail.send_message(to=recipient, subject=subject, body_text=body)
    except Exception as e:
        logger.exception("send_interview_invitation lỗi khi gửi qua Gmail (candidate_id=%s)", candidate_id)
        error_text = str(e)
        with SessionLocal() as session:
            session.add(
                SentEmail(
                    candidate_id=candidate_id,
                    recipient_email=recipient,
                    subject=subject,
                    body=body,
                    gmail_message_id=None,
                    status="failed",
                    error_message=error_text,
                    batch_id=batch_id,
                )
            )
            session.commit()
        return {"success": False, "message_id": None, "error": error_text}

    with SessionLocal() as session:
        session.add(
            SentEmail(
                candidate_id=candidate_id,
                recipient_email=recipient,
                subject=subject,
                body=body,
                gmail_message_id=message_id,
                status="success",
                batch_id=batch_id,
            )
        )
        session.commit()

    logger.info("Đã gửi + ghi log email mời PV cho caididate_id=%s", candidate_id)
    return {"success": True, "message_id": message_id, "error": None}
