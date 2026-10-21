"""Outbox consumer: commit the send claim before any Gmail side effect.

A worker redelivery never sends a record already marked sending/unknown/success.
An ambiguous provider outcome requires reconciliation, not an automatic retry.
"""
import logging
from datetime import timedelta

from googleapiclient.errors import HttpError
from sqlalchemy import select, update

from src.db import session as db_session
from src.db.models import AppUser, Candidate, InvitationBatch, InvitationDelivery, SentEmail
from src.ingestion.email_intake.gmail_client import GmailClient
from src.notification.invitations import now

logger = logging.getLogger(__name__)


def message_reference(delivery_id):
    return f"invitation-{delivery_id}@cv-rag.local"


def finish(delivery_id, status, *, message_id=None, error_code=None):
    with db_session.SessionLocal() as db:
        row = db.scalar(select(InvitationDelivery).where(InvitationDelivery.delivery_id == delivery_id).with_for_update())
        if row is None or (row.status == "success" and status != "success"):
            return
        row.status, row.gmail_message_id, row.error_code, row.finished_at = status, message_id, error_code, now()
        log = db.scalar(select(SentEmail).where(SentEmail.delivery_id == delivery_id))
        if log:
            log.status, log.gmail_message_id, log.error_message, log.sent_at = status, message_id, error_code, now()
        db.commit()


def deliver(delivery_id):
    with db_session.SessionLocal() as db:
        claimed = db.execute(update(InvitationDelivery).where(InvitationDelivery.delivery_id == delivery_id,
            InvitationDelivery.status == "queued").values(status="sending", attempts=InvitationDelivery.attempts + 1,
                started_at=now(), error_code=None)).rowcount
        if not claimed:
            return
        row = db.get(InvitationDelivery, delivery_id)
        batch = db.get(InvitationBatch, row.batch_id)
        user = db.get(AppUser, batch.approved_by) if batch and batch.approved_by else None
        candidate = db.get(Candidate, row.candidate_id)
        allowed = bool(user and user.is_active and user.role == "admin")
        recipient_current = bool(candidate and (candidate.email or "").strip() == row.recipient_email)
        payload = {"to": row.recipient_email, "subject": row.subject, "body_text": row.body,
                   "rfc_message_id": message_reference(delivery_id)}
        log = db.scalar(select(SentEmail).where(SentEmail.delivery_id == delivery_id))
        if log: log.status = "sending"
        if batch: batch.dispatch_error = None
        db.commit()
    if not allowed or not recipient_current:
        finish(delivery_id, "failed", error_code="APPROVAL_REVOKED" if not allowed else "RECIPIENT_CHANGED")
        return
    try:
        gmail = GmailClient(interactive=False)
    except Exception as exc:
        logger.warning("Gmail setup failed: %s", type(exc).__name__)
        finish(delivery_id, "failed", error_code="GMAIL_SETUP_FAILED")
        return
    try:
        message_id = gmail.send_message(**payload)
    except HttpError as exc:
        code = getattr(exc.resp, "status", 0)
        rejected = 400 <= code < 500 and code != 408
        finish(delivery_id, "failed" if rejected else "unknown",
               error_code="GMAIL_REJECTED" if rejected else "DELIVERY_UNCONFIRMED")
    except Exception as exc:
        logger.warning("Gmail send outcome unknown: %s", type(exc).__name__)
        finish(delivery_id, "unknown", error_code="DELIVERY_UNCONFIRMED")
    else:
        if message_id:
            finish(delivery_id, "success", message_id=message_id)
        else:
            finish(delivery_id, "unknown", error_code="DELIVERY_UNCONFIRMED")


def process_batch(batch_id):
    with db_session.SessionLocal() as db:
        ids = db.scalars(select(InvitationDelivery.delivery_id).where(InvitationDelivery.batch_id == batch_id,
            InvitationDelivery.status == "queued").order_by(InvitationDelivery.created_at, InvitationDelivery.delivery_id)).all()
    for identifier in ids:
        # If DB logging fails after Gmail accepts a message, stop this delivery.
        # The persisted sending claim prevents duplicate sends on task redelivery.
        try:
            deliver(identifier)
        except Exception as exc:
            logger.error("Invitation processing interrupted: %s", type(exc).__name__)
    return {"batch_id": batch_id}


def drain_outbox():
    with db_session.SessionLocal() as db:
        stale = db.scalars(select(InvitationDelivery.delivery_id).where(InvitationDelivery.status == "sending",
            InvitationDelivery.started_at < now() - timedelta(minutes=10))).all()
        batches = db.scalars(select(InvitationDelivery.batch_id).where(InvitationDelivery.status == "queued").distinct().limit(20)).all()
    for identifier in stale:
        finish(identifier, "unknown", error_code="DELIVERY_UNCONFIRMED")
    for identifier in batches:
        process_batch(identifier)
    return {"batches": len(batches)}
