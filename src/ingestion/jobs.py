"""Durable upload intake and safe, admin-only job inspection/recovery."""
import logging
import uuid
from datetime import datetime, timezone
import urllib3
from sqlalchemy import select
from src.auth.service import require_admin
from src.config.settings import get_settings
from src.db import session as database
from src.db.models import IngestionJob, JobPosting, Department, Candidate
from src.ingestion.email_intake.validators import compute_content_hash, run_all_validations
from src.ingestion.locking import named_lock
from src.management.errors import ManagementError
from src.management.service import page_result
from src.storage.minio_client import MinioStorage

logger = logging.getLogger(__name__)
settings = get_settings()
HARD_MAX_BYTES = 50 * 1024 * 1024
STATUS = ("pending", "processing", "failed", "dlq", "rejected", "indexed")


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def capabilities():
    require_admin()
    return dict(extensions=["pdf"], min_bytes=settings.CV_MIN_FILE_SIZE_BYTES,
                max_bytes=min(settings.CV_MAX_FILE_SIZE_BYTES, HARD_MAX_BYTES), max_pages=settings.CV_MAX_PAGES,
                filename_pattern=settings.CV_FILENAME_PATTERN, filename_example="NguyenVanA_DataEngineer_CV.pdf")


def storage_client():
    return MinioStorage(http_client=urllib3.PoolManager(timeout=urllib3.Timeout(connect=3, read=30), retries=False))


def publish(job_id):
    error = None
    try:
        from src.workers.celery_app import celery_app
        celery_app.send_task("src.workers.tasks_ingestion.process_cv_job", args=[job_id], ignore_result=True, retry=False)
    except Exception as exc:
        error = "QUEUE_UNAVAILABLE"
        logger.warning("Ingestion queue failed: %s", type(exc).__name__)
    with database.SessionLocal() as db:
        job = db.get(IngestionJob, job_id)
        if job:
            job.dispatch_error = error
            db.commit()


def accept(file_bytes, filename, *, posting_id=None, uploaded_by=None, source_type="web_upload", source_reference=None):
    # Internal intake primitive. The HTTP entry point below always rechecks
    # authorization and supplies the authenticated uploader, never client input.
    if not filename or len(filename) > 255 or "/" in filename or "\\" in filename or any(ord(c) < 32 for c in filename):
        raise ManagementError("INVALID_FILENAME", "Tên file không hợp lệ.", 422)
    if len(file_bytes) > min(settings.CV_MAX_FILE_SIZE_BYTES, HARD_MAX_BYTES):
        raise ManagementError("FILE_TOO_LARGE", "File vượt quá dung lượng cho phép.", 413)
    result = run_all_validations(filename, file_bytes)
    if not result.is_valid:
        code = (result.reason or "invalid_pdf").split(":", 1)[0].upper()
        messages = {
            "INVALID_FILENAME_FORMAT": "Tên file cần theo mẫu: NguyenVanA_DataEngineer_CV.pdf.",
            "FILE_TOO_SMALL": "File nhỏ hơn dung lượng tối thiểu.",
            "PDF_TOO_MANY_PAGES": "PDF vượt quá số trang cho phép.",
            "PDF_IS_ENCRYPTED": "PDF có mật khẩu. Hãy dùng bản không mã hóa.",
        }
        raise ManagementError(code, messages.get(code, "File PDF không hợp lệ hoặc bị hỏng."), 422)
    file_hash = compute_content_hash(file_bytes)
    with named_lock("file:" + file_hash) as locked:
        if not locked:
            raise ManagementError("UPLOAD_IN_PROGRESS", "File này đang được tiếp nhận. Hãy xem danh sách tác vụ rồi thử lại.")
        with database.SessionLocal() as db:
            if posting_id:
                posting = db.get(JobPosting, posting_id)
                if posting is None or not posting.is_active:
                    raise ManagementError("POSTING_UNAVAILABLE", "Vị trí không tồn tại hoặc đã ngừng tuyển.", 422)
            existing = db.scalar(select(IngestionJob).where(IngestionJob.file_hash == file_hash))
            if existing:
                if existing.posting_id != posting_id:
                    raise ManagementError("FILE_ALREADY_ASSIGNED", "File đã được tiếp nhận cho vị trí khác. Hãy mở hồ sơ/tác vụ cũ để kiểm tra.")
                return existing.job_id
            job_id = str(uuid.uuid4())
            storage = None
            try:
                storage = storage_client()
                key = storage.build_object_key(job_id, filename)
                storage.upload_bytes(key, file_bytes)
            except Exception as exc:
                logger.warning("CV upload storage failed: %s", type(exc).__name__)
                raise ManagementError("STORAGE_UNAVAILABLE", "Chưa lưu được file. Kiểm tra MinIO rồi thử lại.", 503) from None
            db.add(IngestionJob(job_id=job_id, source_type=source_type, source_reference=source_reference or "web",
                minio_bucket=storage.bucket, minio_object_key=key, original_filename=filename, file_type="pdf",
                status="pending", file_hash=file_hash, posting_id=posting_id, uploaded_by=uploaded_by))
            db.commit()
        publish(job_id)
        return job_id


def upload(file_bytes, filename, posting_id):
    user = require_admin()
    job_id = accept(file_bytes, filename, posting_id=posting_id, uploaded_by=user.user_id)
    return detail(job_id)


def job_view(db, job):
    posting = db.get(JobPosting, job.posting_id) if job.posting_id else None
    dept = db.get(Department, posting.department_id) if posting else None
    candidate = db.get(Candidate, job.candidate_id) if job.candidate_id else None
    error_code = job.error_code
    if not error_code and job.error_message:
        # Legacy rows can contain provider keys, SQL or CV text. Never echo it.
        prefix = job.error_message.split(":", 1)[0]
        error_code = "DUPLICATE_CV" if prefix.startswith("duplicate_content") else "CV_REJECTED" if job.status == "rejected" else "INGESTION_FAILED"
    return dict(job_id=job.job_id, original_filename=job.original_filename, source_type=job.source_type,
                status=job.status, attempts=job.attempts, max_attempts=job.max_attempts,
                error_code=error_code, dispatch_error=job.dispatch_error, created_at=job.created_at,
                updated_at=job.updated_at, started_at=job.started_at, candidate_id=job.candidate_id,
                candidate_name=candidate.full_name if candidate else None, posting_id=job.posting_id,
                position_title=posting.position_title if posting else None,
                department_name=dept.department_name if dept else None,
                can_retry=job.status in ("pending", "failed", "dlq", "processing") and bool(job.minio_object_key))


def listing(*, page=1, page_size=20, q=None, status=None, source_type=None):
    require_admin()
    query = select(IngestionJob)
    if q:
        query = query.where(IngestionJob.original_filename.icontains(q, autoescape=True))
    if status:
        query = query.where(IngestionJob.status == status)
    if source_type:
        query = query.where(IngestionJob.source_type == source_type)
    with database.SessionLocal() as db:
        return page_result(db, query.order_by(IngestionJob.created_at.desc(), IngestionJob.job_id), page, page_size, lambda row: job_view(db, row[0]))


def detail(job_id):
    require_admin()
    with database.SessionLocal() as db:
        job = db.get(IngestionJob, job_id)
        if job is None:
            raise ManagementError("JOB_NOT_FOUND", "Không tìm thấy tác vụ.", 404)
        return job_view(db, job)


def retry(job_id):
    require_admin()
    with named_lock("job:" + job_id) as locked:
        if not locked:
            raise ManagementError("JOB_RUNNING", "Tác vụ vẫn đang chạy. Hãy chờ kết quả.")
        with database.SessionLocal() as db:
            job = db.get(IngestionJob, job_id)
            if job is None:
                raise ManagementError("JOB_NOT_FOUND", "Không tìm thấy tác vụ.", 404)
            if job.status in ("indexed", "rejected") or not job.minio_object_key:
                raise ManagementError("JOB_NOT_RETRYABLE", "Tác vụ hoàn tất hoặc file bị từ chối không thể thử lại.")
            if job.status in ("dlq", "processing"):
                job.attempts = 0
            job.status, job.error_code, job.error_message, job.started_at = "pending", None, None, None
            db.commit()
    publish(job_id)
    return detail(job_id)
