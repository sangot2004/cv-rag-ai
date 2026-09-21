import logging

from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="src.workers.tasks_notification.send_bulk_emails")
def send_bulk_emails(email_batch: list[dict], batch_id: str) -> dict:
    from src.notification.email_sender import send_interview_invitation

    results = {"success": 0, "failed": 0, "details": []}

    for item in email_batch:
        try:
            result = send_interview_invitation(
                item["candidate_id"], item["subject"], item["body"], batch_id=batch_id
            )
            if result["success"]:
                results["success"] += 1
            else:
                results["failed"] += 1
            results["details"].append({"candidate": item["candidate_id"], **result})
        except Exception as e:
            logger.exception(
                "send_bulk_emails: lỗi ngoài dự kiến với candidate_id=%s", item.get("candidate_id")
            )
            results["failed"] += 1
            results["details"].append(
                {"candidate_id": item.get("candidate_id"), "success": False, "error": str(e)}
            )

    logger.info(
        "send_bulk_emails batch_id=%s hoàn tất: %d thành công, %d thất bại (tổng %d)",
        batch_id, results["success"], results["failed"], len(email_batch),
    )
    return results
