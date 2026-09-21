import logging
import uuid

logger = logging.getLogger(__name__)


def dispatch_bulk_emails(email_batch: list[dict]) -> dict:
    from src.workers.celery_app import celery_app

    batch_id = str(uuid.uuid4())
    task = celery_app.send_task(
        "src.workers.tasks_notification.send_bulk_emails", args=[email_batch, batch_id]
    )

    logger.info("Dispatch bulk email batch_id=%s task_id=%s, %d email", batch_id, task.id, len(email_batch))
    return {"batch_id": batch_id, "task_id": task.id, "count": len(email_batch)}


def get_batch_status(batch_id: str) -> dict:
    from src.db.models import SentEmail
    from src.db.session import SessionLocal

    with SessionLocal() as session:
        rows = session.query(SentEmail).filter(SentEmail.batch_id == batch_id).all()
        return {
            "total_logged": len(rows),
            "success": sum(1 for r in rows if r.status == "success"),
            "failed": sum(1 for r in rows if r.status == "failed"),
            "details": [
                {
                    "candidate_id": r.candidate_id,
                    "status": r.status,
                    "error_message": r.error_message,
                }
                for r in rows
            ],
        }
