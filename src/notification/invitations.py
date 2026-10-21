"""Admin invitation drafts, frozen approvals, persistent outbox and history."""
import hashlib
import json
import logging
import re
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from threading import Lock
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from src.auth.service import require_admin
from src.candidates.errors import CandidateNotFound
from src.chat.errors import DependencyUnavailable
from src.db import session as db_session
from src.db.models import AppUser, Candidate, InvitationBatch, InvitationDelivery, InvitationDraft, InvitationRecipientGuard, SentEmail
from src.notification.errors import InvitationConflict, InvitationNotFound

logger = logging.getLogger(__name__)
_guard = Lock()
_generating = set()


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def email_valid(value):
    return bool(value and len(value) <= 255 and re.fullmatch(r"[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+", value))


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _get(db, model, identifier, *, lock=False):
    key = getattr(model, next(iter(model.__table__.primary_key)).name)
    statement = select(model).where(key == identifier)
    row = db.scalar(statement.with_for_update() if lock else statement)
    if row is None:
        raise InvitationNotFound()
    return row


def _conflict(code, message):
    raise InvitationConflict(code, message)


def _generating_draft(draft_id):
    with _guard:
        return draft_id in _generating


@contextmanager
def _generation(draft_id):
    with _guard:
        if draft_id in _generating:
            _conflict("DRAFT_BUSY", "Nháp đang được tạo. Hãy tải lại trạng thái.")
        _generating.add(draft_id)
    try:
        yield
    finally:
        with _guard:
            _generating.discard(draft_id)


def _editable(db, draft, expected_revision):
    batch = _get(db, InvitationBatch, draft.batch_id)
    if batch.approval_hash:
        _conflict("BATCH_ALREADY_APPROVED", "Đợt này đã được duyệt gửi; không thể sửa nháp.")
    if draft.revision != expected_revision:
        _conflict("STALE_EMAIL_DRAFT", "Nháp đã thay đổi. Hãy tải lại trước khi thao tác.")
    return batch


def _previous(db, candidate_id, recipient, *, lock=False):
    statement = select(SentEmail.id).where(SentEmail.status == "success", or_(
        SentEmail.candidate_id == candidate_id, func.lower(SentEmail.recipient_email) == (recipient or "").casefold())).limit(1)
    return db.scalar(statement.with_for_update() if lock else statement) is not None


def _lock_recipients(db, recipients):
    # Serialize approval by destination, including different candidates sharing
    # an address. Locking reads below see current data under MySQL REPEATABLE READ.
    for recipient in sorted({value.casefold() for value in recipients if value}):
        row = db.scalar(select(InvitationRecipientGuard).where(
            InvitationRecipientGuard.recipient_email == recipient).with_for_update())
        if row is None:
            try:
                with db.begin_nested():
                    db.add(InvitationRecipientGuard(recipient_email=recipient))
                    db.flush()
            except IntegrityError:
                db.scalar(select(InvitationRecipientGuard).where(
                    InvitationRecipientGuard.recipient_email == recipient).with_for_update())


def _draft_dto(db, draft, candidate):
    return {"draft_id": draft.draft_id, "candidate_id": draft.candidate_id, "full_name": candidate.full_name,
        "recipient_email": draft.recipient_email, "subject": draft.subject, "body": draft.body,
        "revision": draft.revision, "error_code": draft.error_code, "is_generating": _generating_draft(draft.draft_id),
        "ready": email_valid(draft.recipient_email) and bool(draft.subject.strip() and draft.body.strip()),
        "previously_sent": _previous(db, draft.candidate_id, draft.recipient_email)}


def _delivery_status(row):
    # A crashed worker must remain reconcilable even when beat is not running.
    # Unknown does not claim that the mail failed or authorize another send.
    if row.status == "sending" and row.started_at and row.started_at < now() - timedelta(minutes=10):
        return "unknown"
    return row.status


def _summary(db, batch):
    deliveries = db.scalars(select(InvitationDelivery).where(InvitationDelivery.batch_id == batch.batch_id)).all()
    counts = {status: 0 for status in ("queued", "sending", "success", "failed", "unknown")}
    counts.update(Counter(_delivery_status(row) for row in deliveries))
    status = "draft"
    if batch.approval_hash:
        status = "sending" if counts["sending"] else "queued" if counts["queued"] else "completed" if not counts["failed"] and not counts["unknown"] else "needs_attention"
    return {"batch_id": batch.batch_id, "kind": batch.kind, "name": batch.name, "position": batch.position,
        "interview_details": batch.interview_details, "status": status, "total": len(deliveries),
        "counts": counts, "dispatch_error": batch.dispatch_error, "created_at": batch.created_at}


def _batch(db, batch):
    drafts = db.execute(select(InvitationDraft, Candidate).join(Candidate, InvitationDraft.candidate_id == Candidate.candidate_id)
        .where(InvitationDraft.batch_id == batch.batch_id).order_by(InvitationDraft.draft_id)).all()
    deliveries = db.execute(select(InvitationDelivery, Candidate.full_name).join(Candidate, InvitationDelivery.candidate_id == Candidate.candidate_id)
        .where(InvitationDelivery.batch_id == batch.batch_id).order_by(InvitationDelivery.created_at, InvitationDelivery.delivery_id)).all()
    return {**_summary(db, batch), "drafts": [_draft_dto(db, d, c) for d, c in drafts],
        "deliveries": [{"delivery_id": d.delivery_id, "draft_id": d.draft_id, "candidate_id": d.candidate_id,
            "full_name": name, "recipient_email": d.recipient_email, "subject": d.subject, "status": _delivery_status(d),
            "attempts": d.attempts, "error_code": d.error_code or ("DELIVERY_UNCONFIRMED" if _delivery_status(d) == "unknown" else None), "gmail_message_id": d.gmail_message_id,
            "started_at": d.started_at, "finished_at": d.finished_at} for d, name in deliveries]}


def get_batch(batch_id):
    require_admin()
    with db_session.SessionLocal() as db:
        return _batch(db, _get(db, InvitationBatch, batch_id))


def create_batch(**data):
    user = require_admin()
    fingerprint = _hash({k: v for k, v in data.items() if k != "request_id"})
    with db_session.SessionLocal() as db:
        existing = db.scalar(select(InvitationBatch).where(InvitationBatch.request_id == data["request_id"]))
        if existing:
            if existing.created_by != user.user_id or existing.request_hash != fingerprint:
                _conflict("REQUEST_ID_REUSED", "Mã yêu cầu đã được sử dụng cho nội dung khác.")
            return _batch(db, existing)
        candidates = db.scalars(select(Candidate).where(Candidate.candidate_id.in_(data["candidate_ids"]))).all()
        if len(candidates) != len(data["candidate_ids"]):
            raise CandidateNotFound()
        batch = InvitationBatch(request_id=data["request_id"], request_hash=fingerprint, created_by=user.user_id,
            kind=data["kind"], name=data["name"], position=data["position"], interview_details=data["interview_details"])
        try:
            db.add(batch)
            db.flush()
            for c in candidates:
                db.add(InvitationDraft(batch_id=batch.batch_id, candidate_id=c.candidate_id,
                    recipient_email=(c.email or "").strip() or None))
            db.commit()
        except IntegrityError:
            db.rollback()
            # Concurrent requests with the same durable creation key converge.
            existing = db.scalar(select(InvitationBatch).where(InvitationBatch.request_id == data["request_id"]))
            if existing and existing.created_by == user.user_id and existing.request_hash == fingerprint:
                return _batch(db, existing)
            raise
        return _batch(db, batch)


def save_draft(draft_id, *, expected_revision, subject, body):
    require_admin()
    with db_session.SessionLocal() as db:
        draft = _get(db, InvitationDraft, draft_id)
        _get(db, InvitationBatch, draft.batch_id, lock=True)
        _editable(db, draft, expected_revision)
        changed = db.execute(update(InvitationDraft).where(InvitationDraft.draft_id == draft_id,
            InvitationDraft.revision == expected_revision).values(subject=subject, body=body,
            revision=expected_revision + 1, error_code=None)).rowcount
        if not changed:
            _conflict("STALE_EMAIL_DRAFT", "Nháp đã thay đổi. Hãy tải lại trước khi thao tác.")
        db.commit()
        return _batch(db, _get(db, InvitationBatch, draft.batch_id))


def generate_draft(draft_id, *, expected_revision):
    require_admin()
    with _generation(draft_id):
        with db_session.SessionLocal() as db:
            draft = _get(db, InvitationDraft, draft_id)
            batch = _editable(db, draft, expected_revision)
            candidate_id, position, details = draft.candidate_id, batch.position, batch.interview_details
        try:
            from src.notification.email_drafter import draft_interview_email
            from src.api.schemas.emails import SaveInvitationDraft
            result = draft_interview_email(candidate_id, position, details)
            if result is None:
                raise ValueError("No candidate draft")
            valid = SaveInvitationDraft(expected_revision=expected_revision, subject=result.subject, body=result.body)
        except Exception as exc:
            logger.warning("Invitation generation failed: %s", type(exc).__name__)
            with db_session.SessionLocal() as db:
                db.execute(update(InvitationDraft).where(InvitationDraft.draft_id == draft_id,
                    InvitationDraft.revision == expected_revision).values(error_code="AI_DRAFT_FAILED"))
                db.commit()
            raise DependencyUnavailable() from exc
        require_admin()
        return save_draft(draft_id, **valid.model_dump())


def publish_batch(batch_id):
    """Publish only IDs; the committed DB outbox remains the source of truth."""
    try:
        from src.workers.celery_app import celery_app
        celery_app.send_task("src.workers.tasks_notification.process_invitation_batch", args=[batch_id],
                             ignore_result=True, retry=False)
        error = None
    except Exception as exc:
        logger.warning("Invitation queue unavailable: %s", type(exc).__name__)
        error = "QUEUE_UNAVAILABLE"
    with db_session.SessionLocal() as db:
        db.execute(update(InvitationBatch).where(InvitationBatch.batch_id == batch_id).values(dispatch_error=error))
        db.commit()


def dispatch(batch_id, *, drafts, allow_previous, confirmed):
    user = require_admin()
    if confirmed is not True:
        _conflict("CONFIRMATION_REQUIRED", "Cần xác nhận gửi thư.")
    fingerprint = _hash({"drafts": sorted(drafts, key=lambda d: d["draft_id"]), "allow_previous": allow_previous})
    with db_session.SessionLocal() as db:
        batch = _get(db, InvitationBatch, batch_id, lock=True)
        if batch.approval_hash:
            if batch.approval_hash != fingerprint:
                _conflict("BATCH_ALREADY_APPROVED", "Đợt này đã được duyệt với danh sách/nội dung khác.")
            return _batch(db, batch)
        selected = db.scalars(select(InvitationDraft).where(InvitationDraft.batch_id == batch_id,
            InvitationDraft.draft_id.in_([d["draft_id"] for d in drafts]))).all()
        if not selected or len(selected) != len(drafts):
            raise InvitationNotFound()
        _lock_recipients(db, [d.recipient_email for d in selected])
        candidates = {c.candidate_id: c for c in db.scalars(select(Candidate).where(Candidate.candidate_id.in_(
            [d.candidate_id for d in selected])).order_by(Candidate.candidate_id).with_for_update()).all()}
        revisions = {d["draft_id"]: d["revision"] for d in drafts}
        recipients = set()
        for draft in selected:
            _editable(db, draft, revisions[draft.draft_id])
            recipient = draft.recipient_email
            if not email_valid(recipient) or not draft.subject.strip() or not draft.body.strip():
                _conflict("DRAFT_NOT_READY", "Có thư chưa đủ nội dung hoặc email người nhận không hợp lệ.")
            if (candidates[draft.candidate_id].email or "").strip() != recipient:
                _conflict("RECIPIENT_CHANGED", "Email ứng viên đã thay đổi. Hãy tạo nháp mới để kiểm tra người nhận.")
            if recipient.casefold() in recipients:
                _conflict("DUPLICATE_RECIPIENT", "Có nhiều ứng viên dùng cùng email. Chỉ chọn một thư cho mỗi địa chỉ.")
            recipients.add(recipient.casefold())
            active = db.scalar(select(InvitationDelivery.delivery_id).where(or_(InvitationDelivery.candidate_id == draft.candidate_id,
                func.lower(InvitationDelivery.recipient_email) == recipient.casefold()), InvitationDelivery.status.in_(["queued", "sending", "unknown"])).limit(1).with_for_update())
            if active:
                _conflict("DELIVERY_UNRESOLVED", "Người nhận đang có thư chờ gửi hoặc chưa rõ kết quả. Hãy kiểm tra lịch sử trước.")
            if _previous(db, draft.candidate_id, recipient, lock=True) and not allow_previous:
                _conflict("PREVIOUS_INVITATION", "Có người nhận đã được gửi thư trước đây. Cần xác nhận gửi thêm.")
        for draft in selected:
            delivery = InvitationDelivery(delivery_id=str(uuid4()), batch_id=batch_id, draft_id=draft.draft_id,
                candidate_id=draft.candidate_id, recipient_email=draft.recipient_email, subject=draft.subject, body=draft.body)
            db.add(delivery)
            db.flush()
            db.add(SentEmail(delivery_id=delivery.delivery_id, candidate_id=draft.candidate_id, recipient_email=draft.recipient_email,
                subject=draft.subject, body=draft.body, status="queued", batch_id=batch_id))
        batch.approval_hash = fingerprint
        batch.approved_by = user.user_id
        db.commit()
    publish_batch(batch_id)
    return get_batch(batch_id)


def requeue(batch_id):
    require_admin()
    with db_session.SessionLocal() as db:
        batch = _get(db, InvitationBatch, batch_id)
        if not batch.approval_hash:
            _conflict("BATCH_NOT_APPROVED", "Đợt này chưa được duyệt gửi.")
    publish_batch(batch_id)
    return get_batch(batch_id)


def retry_delivery(delivery_id, *, confirmed, allow_previous):
    require_admin()
    if confirmed is not True:
        _conflict("CONFIRMATION_REQUIRED", "Cần xác nhận gửi lại thư.")
    with db_session.SessionLocal() as db:
        delivery = _get(db, InvitationDelivery, delivery_id, lock=True)
        batch_id = delivery.batch_id
        if delivery.status != "failed":
            # Retries after a lost response never queue another accepted/uncertain send.
            return _batch(db, _get(db, InvitationBatch, batch_id))
        _lock_recipients(db, [delivery.recipient_email])
        candidate = _get(db, Candidate, delivery.candidate_id, lock=True)
        if (candidate.email or "").strip() != delivery.recipient_email:
            _conflict("RECIPIENT_CHANGED", "Email ứng viên đã thay đổi. Hãy tạo và duyệt thư mới.")
        active = db.scalar(select(InvitationDelivery.delivery_id).where(InvitationDelivery.delivery_id != delivery_id,
            or_(InvitationDelivery.candidate_id == delivery.candidate_id, func.lower(InvitationDelivery.recipient_email) == delivery.recipient_email.casefold()),
            InvitationDelivery.status.in_(["queued", "sending", "unknown"])).limit(1).with_for_update())
        if active:
            _conflict("DELIVERY_UNRESOLVED", "Người nhận có thư đang chờ hoặc chưa rõ kết quả.")
        if _previous(db, delivery.candidate_id, delivery.recipient_email, lock=True) and not allow_previous:
            _conflict("PREVIOUS_INVITATION", "Người nhận đã có thư gửi thành công; cần xác nhận gửi thêm.")
        delivery.status, delivery.error_code, delivery.finished_at = "queued", None, None
        batch = _get(db, InvitationBatch, batch_id)
        approver = db.get(AppUser, batch.approved_by) if batch.approved_by else None
        if not approver or not approver.is_active or approver.role != "admin":
            _conflict("APPROVAL_REVOKED", "Quyền duyệt ban đầu không còn hiệu lực. Hãy tạo và duyệt đợt mới.")
        log = db.scalar(select(SentEmail).where(SentEmail.delivery_id == delivery_id))
        log.status, log.error_message = "queued", None
        db.commit()
    publish_batch(batch_id)
    return get_batch(batch_id)


def list_batches(page=1, page_size=20):
    require_admin()
    with db_session.SessionLocal() as db:
        total = db.scalar(select(func.count()).select_from(InvitationBatch))
        rows = db.scalars(select(InvitationBatch).order_by(InvitationBatch.created_at.desc(), InvitationBatch.batch_id)
            .offset((page - 1) * page_size).limit(page_size)).all()
        return {"items": [_summary(db, b) for b in rows], "total": total, "page": page, "page_size": page_size,
                "has_next": page * page_size < total}


def _history_dto(log, full_name, delivery=None, detail=False):
    result = {"id": log.id, "candidate_id": log.candidate_id, "full_name": full_name, "recipient_email": log.recipient_email,
        "subject": log.subject, "status": _delivery_status(delivery) if delivery else log.status, "batch_id": log.batch_id, "delivery_id": log.delivery_id,
        "sent_at": log.sent_at, "gmail_message_id": log.gmail_message_id,
        "error_code": (delivery.error_code or ("DELIVERY_UNCONFIRMED" if _delivery_status(delivery) == "unknown" else None)) if delivery else ("LEGACY_SEND_FAILED" if log.status == "failed" else None)}
    if detail:
        result["body"] = log.body
    return result


def history(**filters):
    require_admin()
    conditions = []
    if filters.get("q"):
        q = filters["q"]
        conditions.append(or_(Candidate.full_name.icontains(q, autoescape=True), SentEmail.recipient_email.icontains(q, autoescape=True),
                              SentEmail.subject.icontains(q, autoescape=True)))
    stale = and_(InvitationDelivery.status == "sending", InvitationDelivery.started_at < now() - timedelta(minutes=10))
    status = filters.get("status")
    if status == "unknown": conditions.append(or_(SentEmail.status == "unknown", stale))
    elif status == "sending": conditions.append(and_(SentEmail.status == "sending", or_(InvitationDelivery.started_at.is_(None), InvitationDelivery.started_at >= now() - timedelta(minutes=10))))
    elif status: conditions.append(SentEmail.status == status)
    for field in ("candidate_id", "batch_id"):
        if filters.get(field): conditions.append(getattr(SentEmail, field) == str(filters[field]))
    if filters.get("date_from"): conditions.append(SentEmail.sent_at >= datetime.combine(filters["date_from"], time.min, ZoneInfo("Asia/Ho_Chi_Minh")).astimezone(timezone.utc).replace(tzinfo=None))
    if filters.get("date_to"): conditions.append(SentEmail.sent_at < datetime.combine(filters["date_to"] + timedelta(days=1), time.min, ZoneInfo("Asia/Ho_Chi_Minh")).astimezone(timezone.utc).replace(tzinfo=None))
    page, page_size = filters.get("page", 1), filters.get("page_size", 20)
    with db_session.SessionLocal() as db:
        base = select(SentEmail, Candidate.full_name, InvitationDelivery).join(Candidate, Candidate.candidate_id == SentEmail.candidate_id).outerjoin(
            InvitationDelivery, InvitationDelivery.delivery_id == SentEmail.delivery_id).where(*conditions)
        total = db.scalar(select(func.count()).select_from(base.subquery()))
        rows = db.execute(base.order_by(SentEmail.sent_at.desc(), SentEmail.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        return {"items": [_history_dto(*row) for row in rows], "total": total, "page": page,
                "page_size": page_size, "has_next": page * page_size < total}


def history_detail(identifier):
    require_admin()
    with db_session.SessionLocal() as db:
        row = db.execute(select(SentEmail, Candidate.full_name, InvitationDelivery).join(Candidate, Candidate.candidate_id == SentEmail.candidate_id)
            .outerjoin(InvitationDelivery, InvitationDelivery.delivery_id == SentEmail.delivery_id).where(SentEmail.id == identifier)).one_or_none()
        if row is None: raise InvitationNotFound()
        return _history_dto(*row, detail=True)


def reconcile_delivery(delivery_id):
    require_admin()
    from src.notification.delivery_worker import GmailClient, finish, message_reference
    with db_session.SessionLocal() as db:
        row = _get(db, InvitationDelivery, delivery_id)
        batch_id = row.batch_id
        if row.status not in ("unknown", "sending"):
            return _batch(db, _get(db, InvitationBatch, batch_id))
        if row.status == "sending" and row.started_at and row.started_at > now() - timedelta(minutes=10):
            _conflict("DELIVERY_IN_PROGRESS", "Thư đang được xử lý. Hãy chờ cập nhật.")
    try:
        message_id = GmailClient(interactive=False).find_sent_message(message_reference(delivery_id))
    except Exception as exc:
        raise DependencyUnavailable() from exc
    if message_id:
        finish(delivery_id, "success", message_id=message_id)
    else:
        finish(delivery_id, "unknown", error_code="DELIVERY_UNCONFIRMED")
    return get_batch(batch_id)
