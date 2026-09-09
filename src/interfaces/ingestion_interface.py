import logging
import uuid

from src.config.settings import get_settings
from src.db.models import IngestionJob, Candidate
from src.db.session import SessionLocal
from src.ingestion.email_intake.validators import compute_content_hash, run_all_validations
from src.storage.minio_client import MinioStorage

logger = logging.getLogger(__name__)
settings = get_settings()


def submit_cv_ingestion(
        file_bytes: bytes,
        filename: str,
        source_type: str = "web_upload",
        source_reference: str | None = None,
) -> dict:
    validation = run_all_validations(filename, file_bytes)
    if not validation.is_valid:
        logger.warning("submit_cv_for_ingestion reject: %s (file=%s)", validation.reason, filename)
        return {"job_id": None, "status": "rejected", "error": validation.reason}

    content_hash = compute_content_hash(file_bytes)
    job_id = str(uuid.uuid4())

    storage = MinioStorage()
    object_key = storage.build_object_key(job_id, filename)

    try:
        with SessionLocal() as session:
            existing = (
                session.query(Candidate.candidate_id)
                .filter(Candidate.content_hash == content_hash)
                .first()
            )
            if existing:
                logger.info("submit_cv_for_ingestion: trùng nội dung với candidate đã có, reject")
                return {"job_id": None, "status": "rejected", "error": "duplicate_content_hash"}

            storage.upload_bytes(object_key, file_bytes)

            job = IngestionJob(
                job_id=job_id,
                source_type=source_type,
                source_reference=source_reference,
                minio_bucket=storage.bucket,
                minio_object_key=object_key,
                original_filename=filename,
                file_type="pdf",
                status="pending",
            )
            session.add(job)
            session.commit()
    except Exception as e:
        logger.exception("submit_cv_for_ingestion lỗi khi ghi job")
        return {"job_id": None, "status": "rejected", "error": str(e)}

    try:
        from src.workers.celery_app import celery_app

        celery_app.send_task("src.workers.tasks_ingestion.process_cv_job", args=[job_id])
    except Exception:
        logger.exception("submit_cv_for_ingestion: dispatch Celery lỗi, job vẫn ở status=pending")

    logger.info("submit_cv_for_ingestion thành công: job_id=%s", job_id)
    return {"job_id": job_id, "status": "pending", "error": None}
