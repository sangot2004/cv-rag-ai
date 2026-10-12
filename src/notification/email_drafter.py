import logging

from langchain_google_genai import ChatGoogleGenerativeAI

from src.ops.telemetry import monitored, UsageCallback
from src.config.settings import get_settings
from src.llm.key_manager import call_with_key_failover
from src.llm.prompt_store import format_prompt
from src.retrieval.sql_query_tool import get_candidate_full_profile
from src.schemas.email_draft_schema import EmailDraft

logger = logging.getLogger(__name__)
settings = get_settings()

def _draft_call(api_key: str, prompt: str) -> EmailDraft:
    llm = ChatGoogleGenerativeAI(model=settings.GEMINI_LLM_MODEL, google_api_key=api_key,
                                 callbacks=[UsageCallback(settings.GEMINI_LLM_MODEL)])
    structured_llm = llm.with_structured_output(EmailDraft)
    return structured_llm.invoke(prompt)


@monitored('email_draft', ref='candidate_id')
def draft_interview_email(candidate_id: str, position: str, interview_details: str) -> EmailDraft | None:
    """CHỈ SOẠN NỘI DUNG, KHÔNG GỬI GÌ CẢ — trả về EmailDraft để hiển thị
    cho HR xem/sửa trước. Việc gửi thật nằm ở
    notification/email_sender.py, chỉ được gọi khi HR bấm nút xác nhận
    trên UI, KHÔNG bao giờ được gọi tự động từ đây hay từ Agent.
    """
    profile = get_candidate_full_profile(candidate_id)
    if profile is None:
        logger.warning("draft_interview_email: candidate_id=%s không tồn tại/ngoài phạm vi", candidate_id)
        return None

    prompt = format_prompt(
        "cv-rag-draft-interview-email",
        candidate_name=profile["full_name"],
        position=position,
        interview_details=interview_details or "(HR chưa cung cấp chi tiết cụ thể)",
    )

    return call_with_key_failover(lambda key: _draft_call(key, prompt))
