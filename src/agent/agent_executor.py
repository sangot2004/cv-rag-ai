import logging

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agent.tools.candidate_detail_tool import get_candidate_detail
from src.agent.tools.certificate_project_tool import (
    find_candidates_by_certificate,
    find_candidates_by_project_tech,
)
from src.agent.tools.compare_tool import compare_candidates
from src.agent.tools.draft_email_tool import draft_interview_invitation
from src.agent.tools.bulk_email_tool import draft_bulk_interview_invitations
from src.agent.tools.evaluation_tool import evaluate_candidate_against_jd
from src.agent.tools.jd_matching_tool import find_top_candidates_for_jd
from src.agent.tools.recent_candidates_tool import list_recent_cvs
from src.agent.tools.search_tool import semantic_search_cv
from src.agent.tools.sql_filter_tool import filter_candidates_sql
from src.agent.tools.stats_tool import count_candidates
from src.config.settings import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """Bạn là trợ lý AI hỗ trợ HR tra cứu và đánh giá ứng viên
trong hệ thống quản lý CV. Bạn có các công cụ để tra cứu dữ liệu ứng viên.

Luôn ưu tiên công cụ filter/tìm kiếm chính xác nếu câu hỏi có thể trả lời
bằng tiêu chí rõ ràng — nhanh và chính xác hơn semantic search. Trả lời
bằng tiếng Việt, ngắn gọn, dựa trên dữ liệu tool trả về — không bịa thông
tin ứng viên không có trong kết quả tool. Nếu câu hỏi tiếp nối hội thoại
trước đó (vd "còn ai khác", "so với người vừa nãy"), dùng ngữ cảnh hội
thoại đã có để hiểu đúng ý người hỏi."""

_tools = [
    filter_candidates_sql,
    semantic_search_cv,
    evaluate_candidate_against_jd,
    get_candidate_detail,
    compare_candidates,
    count_candidates,
    find_candidates_by_certificate,
    find_candidates_by_project_tech,
    list_recent_cvs,
    find_top_candidates_for_jd,
    draft_interview_invitation,
    draft_bulk_interview_invitations,
]


def build_agent_executor(api_key: str, checkpointer=None):
    llm = ChatGoogleGenerativeAI(model=settings.GEMINI_LLM_MODEL, google_api_key=api_key)
    return create_agent(
        model=llm, tools=_tools, system_prompt=SYSTEM_PROMPT, checkpointer=checkpointer
    )
