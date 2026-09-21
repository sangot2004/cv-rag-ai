import logging

from src.notification.email_drafter import draft_interview_email

logger = logging.getLogger(__name__)


def draft_bulk_emails(candidate_ids: list[str], position: str, interview_details: str) -> list[dict]:
    from src.retrieval.sql_query_tool import get_candidate_full_profile

    results = []
    for candidate_id in candidate_ids:
        try:
            profile = get_candidate_full_profile(candidate_id)
            if profile is None:
                results.append(
                    {
                        "candidate_id": candidate_id,
                        "full_name": None,
                        "subject": None,
                        "error": "Không tồn tại hoặc ngoài phạm vi quyền xem",
                    }
                )
                continue

            draft = draft_interview_email(candidate_id, position, interview_details)
            results.append(
                {
                    "candidate_id": candidate_id,
                    "full_name": profile["full_name"],
                    "subject": draft.subject,
                    "body": draft.body,
                    "error": None,
                }
            )
        except Exception as e:
            logger.exception("draft_bulk_emails lỗi với candidate_id=%s", candidate_id)
            results.append(
                {
                    "candidate_id": candidate_id,
                    "full_name": None,
                    "subject": None,
                    "body": None,
                    "error": str(e),
                }
            )

    logger.info(
        "draft_bulk_emails: %d/%d candidate soạn thành công",
        sum(1 for r in results if r["error"] is None), len(candidate_ids),
    )
    return results
