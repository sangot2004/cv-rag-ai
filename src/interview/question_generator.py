import logging
import re

from langchain_google_genai import ChatGoogleGenerativeAI

from src.config.settings import get_settings
from src.db.models import InterviewQuestion
from src.db.session import SessionLocal
from src.interview.prompts import GENERATE_INTERVIEW_QUESTIONS_PROMPT
from src.llm.key_manager import call_with_key_failover
from src.retrieval.sql_query_tool import get_candidate_raw_text
from src.schemas.interview_question_schema import QuestionList

logger = logging.getLogger(__name__)
settings = get_settings()

DEFAULT_MAX_QUESTIONS = 8


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _generate_call(api_key: str, cv_text: str, max_questions: int) -> QuestionList:
    llm = ChatGoogleGenerativeAI(model=settings.GEMINI_LLM_MODEL, google_api_key=api_key)
    structured_llm = llm.with_structured_output(QuestionList)
    prompt = GENERATE_INTERVIEW_QUESTIONS_PROMPT.format(cv_text=cv_text, max_questions=max_questions)
    return structured_llm.invoke(prompt)


def _validate_evidence(question, cv_text_normalized: str) -> bool:
    return _normalize(question.evidence_quote) in cv_text_normalized


class CandidateNotFoundError(Exception):
    pass


class CandidateHasNoCVError(Exception):
    pass


def generate_interview_questions(candidate_id: str, max_questions: int = DEFAULT_MAX_QUESTIONS) -> list[dict]:
    profile = get_candidate_raw_text(candidate_id)
    if profile is None:
        raise CandidateNotFoundError(f"candidate_id={candidate_id} không tồn tại hoặc ngoài phạm vi quyền xem")

    cv_text = profile["raw_text"]
    cv_text_normalized = _normalize(cv_text)

    valid_questions = []
    for attempt in range(2):
        result = call_with_key_failover(lambda key: _generate_call(key, cv_text, max_questions))

        rejected_count = 0
        for q in result.questions:
            if _validate_evidence(q, cv_text_normalized):
                valid_questions.append(q)
            else:
                rejected_count += 1
                logger.warning(
                    "Evidence không khớp CV, loại bỏ câu hỏi (candidate_id=%s): %r",
                    candidate_id, q.evidence_quote[:100],
                )

        logger.info(
            "generate_interview_questions candidate_id=%s: %d hợp lệ, %d bị loại (lần thử %d)",
            candidate_id, len(valid_questions), rejected_count, attempt + 1,
        )

        if valid_questions:
            break
        logger.warning("Toàn bộ câu hỏi bị loại, thử sinh lại lần %d", attempt + 2)

    with SessionLocal() as session:
        session.query(InterviewQuestion).filter(InterviewQuestion.candidate_id == candidate_id).delete()

        saved = []
        for q in valid_questions:
            record = InterviewQuestion(
                candidate_id=candidate_id,
                question_text=q.question,
                category=q.category.value,
                evidence_quote=q.evidence_quote,
                cv_section=q.cv_section,
            )
            session.add(record)
            saved.append(record)

        session.commit()

        return [
            {
                "id": r.id,
                "question": r.question_text,
                "category": r.category,
                "cv_section": r.cv_section,
                "evidence_quote": r.evidence_quote,
            }
            for r in saved
        ]


def get_interview_questions(candidate_id: str) -> list[dict]:
    with SessionLocal() as session:
        rows = (
            session.query(InterviewQuestion)
            .filter(InterviewQuestion.candidate_id == candidate_id)
            .order_by(InterviewQuestion.id)
            .all()
        )
        return [
            {
                "id": r.id,
                "question": r.question_text,
                "category": r.category,
                "cv_section": r.cv_section,
                "evidence_quote": r.evidence_quote,
            }
            for r in rows
        ]


def delete_interview_questions(candidate_id: str) -> int:
    with SessionLocal() as session:
        count = (
            session.query(InterviewQuestion).filter(InterviewQuestion.candidate_id == candidate_id).delete()
        )
        session.commit()
        return count
