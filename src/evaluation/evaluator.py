import logging

from langchain_google_genai import ChatGoogleGenerativeAI

from src.config.settings import get_settings
from src.evaluation.rubric import DEFAULT_CRITERIA, EvaluationResult
from src.retrieval.sql_query_tool import get_candidate_full_profile

logger = logging.getLogger(__name__)
settings = get_settings()

_llm = ChatGoogleGenerativeAI(model=settings.GEMINI_LLM_MODEL, google_api_key=settings.GOOGLE_API_KEY)

EVALUATE_PROMPT = """Đánh giá mức độ phù hợp của ứng viên sau với JD, CHỈ dựa trên
{criteria_list}.
Chấm mỗi tiêu chí thang điểm 1-5, kèm lý do NGẮN GỌN dựa trên dữ liệu CV cụ thể
bên dưới — không suy diễn thông tin CV không có.

JD:
---
{jd}
---

Hồ sơ ứng viên (candidate_id={candidate_id}):
---
{profile}
---"""


def evaluate_candidate(candidate_id: str, job_description: str) -> EvaluationResult | None:
    """đánh giá 1 ứng viên theo jd, dùng rubric cố định để tránh 
    llm chấm điểm cảm tính, không nhất quán giữa các lần gọi."""
    profile = get_candidate_full_profile(candidate_id)
    if profile is None:
        logger.warning("evaluate_candidate: candidate_id=%s không tồn tại", candidate_id)
        return None

    criteria_list = "\n".join(f"- {c}" for c in DEFAULT_CRITERIA)
    prompt = EVALUATE_PROMPT.format(
        criteria_list=criteria_list,
        jd=job_description,
        candidate_id=candidate_id,
        profile=profile,
    )

    structured_llm = _llm.with_structured_output(EvaluationResult)
    result = structured_llm.invoke(prompt)

    logger.info(
        "evaluate_candidate candidate_id=%s overall_score=%.1f", candidate_id, result.overall_score
    )
    return result
