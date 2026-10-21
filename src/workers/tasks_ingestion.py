import logging

from src.db.models import IngestionJob
from src.db.session import SessionLocal
from src.ingestion.pipeline import CVRejected, PipelineBusy, run_ingestion_pipeline
from src.ingestion.locking import named_lock
from src.ingestion.jobs import now
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
    max_retries=None,
    ignore_result=True,
)
def process_cv_job(self, job_id: str) -> None:
    """Claim each job once; keep safe states even if the broker is unavailable."""
    with named_lock("job:" + job_id) as locked:
        if not locked:
            return
        with SessionLocal() as session:
            job = session.get(IngestionJob, job_id)
            if job is None or job.status not in ("pending", "failed"):
                return
            if job.attempts >= job.max_attempts:
                job.status = "dlq"
                session.commit()
                return
            job.status, job.started_at = "processing", now()
            job.attempts += 1
            job.dispatch_error, job.error_code, job.error_message = None, None, None
            session.commit()
        try:
            run_ingestion_pipeline(job_id)
            return
        except PipelineBusy:
            with SessionLocal() as session:
                job = session.get(IngestionJob, job_id)
                job.status, job.started_at = "pending", None
                job.attempts -= 1
                session.commit()
            raise self.retry(countdown=15)
        except CVRejected as exc:
            prefix = exc.reason.split(":", 1)[0]
            code = "DUPLICATE_CV" if prefix.startswith("duplicate_content") else "CV_REJECTED"
            with SessionLocal() as session:
                job = session.get(IngestionJob, job_id)
                job.status, job.error_code, job.error_message = "rejected", code, code
                session.commit()
            return
        except Exception as exc:
            logger.warning("Ingestion failed job_id=%s type=%s", job_id, type(exc).__name__)
            with SessionLocal() as session:
                job = session.get(IngestionJob, job_id)
                # The pipeline can have committed before telemetry failed.
                if job.status == "indexed":
                    return
                job.status = "dlq" if job.attempts >= job.max_attempts else "failed"
                job.error_code = job.error_message = "INGESTION_FAILED"
                exhausted, attempts = job.status == "dlq", job.attempts
                session.commit()
            if not exhausted:
                raise self.retry(countdown=min(60 * (2 ** (attempts - 1)), 900))
