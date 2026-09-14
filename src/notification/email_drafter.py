import logging

from langchain_google_genai import ChatGoogleGenerativeAI

from src.config.settings import get_settings
from src.llm.key_manager import call_with_key_failover
from src.retrieval.sql_query_tool import get_candidate_full_profile
from src.schemas.email_draft_schema import EmailDraft

logger = logging.getLogger(__name__)
settings = get_settings()

DRAFT_EMAIL_PROMPT = """Soạn 1 email mời phỏng vấn gửi cho ứng viên dưới đây,
bằng tiếng Việt, lịch sự, chuyên nghiệp, ngắn gọn.

QUAN TRỌNG: chỉ đưa vào những thông tin đã được cung cấp bên dưới (thời
gian, địa điểm, hình thức phỏng vấn). Nếu thông tin nào KHÔNG được cung
cấp, để trống hoặc ghi placeholder rõ ràng như "[thời gian phỏng vấn]" —
TUYỆT ĐỐI không tự bịa ra ngày giờ/địa điểm cụ thể.

Ứng viên: {candidate_name}
Vị trí ứng tuyển: {position}

Chi tiết phỏng vấn do HR cung cấp:
{interview_details}"""


def _draft_call(api_key: str, prompt: str) -> EmailDraft:
    llm = ChatGoogleGenerativeAI(model=settings.GEMINI_LLM_MODEL, google_api_key=api_key)
    structured_llm = llm.with_structured_output(EmailDraft)
    return structured_llm.invoke(prompt)


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

    prompt = DRAFT_EMAIL_PROMPT.format(
        candidate_name=profile["full_name"],
        position=position,
        interview_details=interview_details or "(HR chưa cung cấp chi tiết cụ thể)",
    )

    return call_with_key_failover(lambda key: _draft_call(key, prompt))
