import logging
import uuid
import redis

from src.config.settings import get_settings
from src.db.models import IngestionJob
from src.db.session import SessionLocal
from src.ingestion.email_intake.gmail_client import EmailAttachment, EmailMessage, GmailClient
from src.ingestion.email_intake.validators import (
    compute_content_hash, run_all_validations
)
from src.storage.minio_client import MinioStorage

logger = logging.getLogger(__name__)
settings = get_settings()


class EmailIntakePipeline:
    def __init__(self, dry_run: bool = False):
        """dry_run = true: run gmail + validate + upload MinIO, nhưng k ghi vào sql(test)"""
        self.gmail = GmailClient()
        self.storage = MinioStorage()
        self.redis = redis.from_url(settings.REDIS_URL)
        self.dry_run = dry_run

    def run_once(self) -> dict:
        """Poll 1 lần, xử lý toàn bộ mail mới. xử lý định kỳ"""
        stats = {"scanned": 0, "accepted": 0, "rejected": 0, "skipped_duplicate": 0}
        message_ids = self.gmail.list_new_messages()
        stats["scanned"] = len(message_ids)

        for message_id in message_ids:
            if not self._acquire_message_lock(message_id):
                stats["skipped_duplicate"] += 1
                continue

            try:
                email = self.gmail.fetch_message_with_attachments(message_id)
                result = self._process_email(email)
                stats["accepted"] += result["accepted"]
                stats["rejected"] += result["rejected"]
            except Exception:
                logger.exception("Failed processing message_id=%s", message_id)
            finally:
                # Mark đã đọc dù thành công hay lỗi, tránh loop
                self.gmail.mark_as_processed(message_id)

        return stats

    def _acquire_message_lock(self, message_id: str) -> bool:
        """1.2 dedupe theo masage_id, trnahs gọi trùng"""
        key = f"email_intake:processed:{message_id}"
        return bool(self.redis.set(key, "1", nx=True, ex=settings.DEDUPE_MESSAGE_TTL_SECONDS))

    def _process_email(self, email: EmailMessage) -> dict:
        accepted, rejected = 0, 0

        pdf_attachments = [a for a in email.attachments if a.filename.lower().endswith(".pdf")]

        if not pdf_attachments:
            logger.info("Message %s has no PDF attachment, skip.", email.message_id)
            return {"accepted": 0, "rejected": 0}

        for attachment in pdf_attachments:
            ok = self._process_attachment(email, attachment)
            if ok:
                accepted += 1
            else:
                rejected += 1

        return {"accepted": accepted, "rejected": rejected}

    def _process_attachment(self, email: EmailMessage, attachment: EmailAttachment) -> bool:
        validation = run_all_validations(attachment.filename, attachment.data)

        if not validation.is_valid:
            logger.warning(
                "Rejected %s from %s: %s", attachment.filename, email.sender, validation.reason
            )
            if not self.dry_run:
                with SessionLocal() as session:
                    self._save_rejected_job(session, email, attachment, validation.reason)
            return False

        content_hash = compute_content_hash(attachment.data)
        job_id = str(uuid.uuid4)
        object_key = self.storage.build_object_key(job_id, attachment.filename)

        if self.dry_run:
            logger.info(
                "[DRY RUN] Would upload %s -> %s (hash=%s, job_id=%s) - MySQL write skipped",
                attachment.filename, object_key, content_hash[:12], job_id,
            )
            self.storage.upload_bytes(object_key, attachment.data)
            return True

        with SessionLocal() as session:
            if self._is_duplicate_content(session, content_hash):
                self._save_rejected_job(session, email, attachment, "duplicate_content_hash")
                logger.info("Duplicate CV skipped: %s", attachment.filename)
                return False

            self.storage.upload_bytes(object_key, attachment.data)

            job = IngestionJob(
                job_id=job_id,
                source_type="email",
                source_reference=email.message_id,
                minio_bucket=settings.MINIO_BUCKET,
                minio_object_key=object_key,
                original_filename=attachment.filename,
                file_type="pdf",
                status="pending",
            )
            session.add(job)
            session.commit()

            logger.info("Accepted CV job_id=%s file=%s", job_id, attachment.filename)
            return True

    @staticmethod
    def is_duplicate_content(session, content_hash: str) -> bool:
        from src.db.models import Candidate

        existing = (
            session.query(Candidate.candidate_id)
            .filter(Candidate.content_hash == content_hash)
            .first()
        )
        return existing is not None

    @staticmethod
    def _save_rejected_job(session, email: EmailMessage, attachment: EmailAttachment, reason: str) -> None:
        job = IngestionJob(
            job_id=str(uuid.uuid4()),
            source_type="email",
            source_reference=email.message_id,
            minio_bucket=settings.MINIO_BUCKET,
            minio_object_key="",
            original_filename=attachment.filename,
            file_type="pdf",
            status="rejected",
            error_message=reason,
        )
        session.add(job)
        session.commit()
