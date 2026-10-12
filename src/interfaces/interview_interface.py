import logging

from src.auth.service import admin_only
from src.interview.question_generator import (
    CandidateNotFoundError,
    CandidateHasNoCVError,
    delete_interview_questions,
    generate_interview_questions,
    get_interview_questions,
)

logger = logging.getLogger(__name__)


@admin_only
def generate_questions_for_candidate(candidate_id: str, max_questions: int = 8) -> dict:
    try:
        questions = generate_interview_questions(candidate_id, max_questions=max_questions)
        return {"questions": questions, "error": None}
    except CandidateNotFoundError as e:
        return {"questions": [], "error": str(e)}
    except CandidateHasNoCVError as e:
        return {"questions": [], "error": str(e)}
    except Exception as e:
        logger.exception("generate_questions_for_candidate lỗi với candidate_id=%r", candidate_id)
        return {"questions": [], "error": str(e)}


@admin_only
def get_questions_for_candidate(candidate_id: str) -> dict:
    try:
        questions = get_interview_questions(candidate_id)
        return {"questions": questions, "error": None}
    except Exception as e:
        logger.exception("get_questions_for_candidate lỗi với candidate_id=%r", candidate_id)
        return {"questions": [], "error": str(e)}


@admin_only
def delete_questions_for_candidate(candidate_id: str) -> dict:
    try:
        count = delete_interview_questions(candidate_id)
        return {"deleted": count, "error": None}
    except Exception as e:
        logger.exception("delete_questions_for_candidate lỗi với candidate_id=%r", candidate_id)
        return {"deleted": 0, "error": str(e)}
