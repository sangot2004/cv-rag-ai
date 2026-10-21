import logging
import re

from langchain_google_genai import ChatGoogleGenerativeAI

from src.ops.telemetry import monitored, UsageCallback
from src.config.settings import get_settings
from src.db.models import InterviewQuestion
from src.db.session import SessionLocal
from src.llm.key_manager import call_with_key_failover
from src.llm.prompt_store import format_prompt
from src.retrieval.sql_query_tool import get_candidate_raw_text
from src.schemas.interview_question_schema import QuestionList
from src.interview.errors import NoValidInterviewQuestions
from src.interview.concurrency import interview_lock

logger = logging.getLogger(__name__)
settings = get_settings()

DEFAULT_MAX_QUESTIONS = 8


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _generate_call(api_key: str, cv_text: str, max_questions: int) -> QuestionList:
    llm = ChatGoogleGenerativeAI(model=settings.GEMINI_LLM_MODEL, google_api_key=api_key,
                                 callbacks=[UsageCallback(settings.GEMINI_LLM_MODEL)])
    structured_llm = llm.with_structured_output(QuestionList)
    prompt = format_prompt(
        "cv-rag-generate-interview-questions",
        cv_text=cv_text, max_questions=max_questions
    )
    return structured_llm.invoke(prompt)


def _validate_evidence(question, cv_text_normalized: str) -> bool:
    quote = _normalize(question.evidence_quote)
    return bool(quote and question.question.strip() and question.cv_section.strip() and quote in cv_text_normalized)


class CandidateNotFoundError(Exception):
    pass


class CandidateHasNoCVError(Exception):
    pass


@monitored('interview_questions', ref='candidate_id')
def build_interview_questions(candidate_id: str, cv_text: str, max_questions: int) -> list:
    """Generate and validate before opening any replacement transaction."""
    if type(max_questions) is not int or not 3 <= max_questions <= 15:
        raise ValueError("Số câu hỏi phải từ 3 đến 15.")
    if not cv_text or not cv_text.strip():
        raise CandidateHasNoCVError("Ứng viên chưa có nội dung CV để sinh câu hỏi.")
    cv_text_normalized = _normalize(cv_text)
    valid_questions = []
    for attempt in range(2):
        result = call_with_key_failover(lambda key: _generate_call(key, cv_text, max_questions))
        seen = set()
        for q in result.questions:
            normalized_question = _normalize(q.question)
            if _validate_evidence(q, cv_text_normalized) and normalized_question not in seen:
                valid_questions.append(q)
                seen.add(normalized_question)
                if len(valid_questions) >= max_questions:
                    break
        logger.info("interview candidate_id=%s valid=%d attempt=%d",
                    candidate_id, len(valid_questions), attempt + 1)
        if valid_questions:
            break
    if not valid_questions:
        raise NoValidInterviewQuestions("Chưa sinh được câu hỏi có trích dẫn hợp lệ. Bộ đã lưu được giữ nguyên.")
    return valid_questions


def generate_interview_questions(candidate_id: str, max_questions: int = DEFAULT_MAX_QUESTIONS) -> list[dict]:
    with interview_lock(candidate_id, generating=True):
        profile = get_candidate_raw_text(candidate_id)
        if profile is None:
            raise CandidateNotFoundError("Ứng viên không tồn tại, chưa có CV hoặc ngoài phạm vi xem.")
        valid_questions = build_interview_questions(candidate_id, profile["raw_text"], max_questions)
        with SessionLocal() as session:
            session.query(InterviewQuestion).filter(InterviewQuestion.candidate_id == candidate_id).delete()
            saved = []
            for q in valid_questions:
                record = InterviewQuestion(candidate_id=candidate_id, question_text=q.question,
                    category=q.category.value, evidence_quote=q.evidence_quote, cv_section=q.cv_section)
                session.add(record)
                saved.append(record)
            session.commit()
            return [{"id": r.id, "question": r.question_text, "category": r.category,
                     "cv_section": r.cv_section, "evidence_quote": r.evidence_quote} for r in saved]


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
    with interview_lock(candidate_id), SessionLocal() as session:
        count = (
            session.query(InterviewQuestion).filter(InterviewQuestion.candidate_id == candidate_id).delete()
        )
        session.commit()
        return count
