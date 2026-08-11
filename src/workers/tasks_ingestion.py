import logging

from src.db.models import IngestionJob
from src.db.session import SessionLocal
from src.ingestion.pipeline import CVIngestionError, CVRejected, run_ingestion_pipeline
from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="src.workers.tasks_ingestion.poll_email_intake")
def poll_email_intake() -> dict:
    """Chạy định kỳ qua Celery Beat (xem beat_schedule trong celery_app.py)."""
    from src.ingestion.email_intake.intake_pipeline import EmailIntakePipeline

    pipeline = EmailIntakePipeline(dry_run=False)
    stats = pipeline.run_once()
    logger.info("poll_email_intake finished: %s", stats)
    return stats


@celery_app.task(
    name="src.workers.tasks_ingestion.process_cv_job",
    bind=True,
    max_retries=3,
)
def process_cv_job(self, job_id: str) -> None:
    """Luồng A + B đầy đủ: parse -> classify -> extract -> chunk -> embed -> index.

    Retry logic tự quản (không dùng autoretry_for chung chung nữa) để phân
    biệt rõ 2 loại lỗi:
      - CVRejected: lỗi bản chất (không phải CV, file hỏng, thiếu field...)
        -> set status='rejected' NGAY, không retry vô ích.
      - Exception khác: lỗi tạm thời (mạng, MinIO, LLM timeout...)
        -> tăng attempts, retry có backoff, vượt max_attempts thì chuyển 'dlq'.
    """
    logger.info("process_cv_job bắt đầu job_id=%s", job_id)

    try:
        candidate_id = run_ingestion_pipeline(job_id)
        logger.info("process_cv_job thành công job_id=%s candidate_id=%s", job_id, candidate_id)
        return

    except CVRejected as e:
        logger.warning("Job %s bị reject: %s", job_id, e.reason)
        with SessionLocal() as session:
            job = session.get(IngestionJob, job_id)
            if job:
                job.status = "rejected"
                job.error_message = e.reason
                session.commit()
        return  # không retry — lỗi bản chất, retry lại vẫn sai

    except Exception as e:
        with SessionLocal() as session:
            job = session.get(IngestionJob, job_id)
            if job is None:
                logger.error("job_id=%s không tồn tại, bỏ qua", job_id)
                return

            job.attempts += 1

            if job.attempts >= job.max_attempts:
                job.status = "dlq"
                job.error_message = f"vuot_max_attempts: {e}"
                session.commit()
                logger.error("Job %s vượt max_attempts (%d), chuyển DLQ", job_id, job.max_attempts)
                return

            job.status = "failed"
            job.error_message = str(e)
            session.commit()
            attempts_now = job.attempts
            max_attempts_now = job.max_attempts

        logger.warning(
            "Job %s lỗi (lần thử %d/%s), sẽ retry: %s", job_id, attempts_now, max_attempts_now, e
        )
        raise self.retry(exc=e, countdown=min(60 * (2 ** self.request.retries), 900))
