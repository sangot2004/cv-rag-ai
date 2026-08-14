import logging

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agent.tools.evaluation_tool import evaluate_candidate_against_jd
from src.agent.tools.search_tool import semantic_search_cv
from src.agent.tools.sql_filter_tool import filter_candidates_sql
from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """Bạn là trợ lý AI hỗ trợ HR tra cứu và đánh giá ứng viên
trong hệ thống quản lý CV. Bạn có 3 công cụ:

1. filter_candidates_sql — dùng khi câu hỏi có tiêu chí CHÍNH XÁC (kỹ năng cụ
   thể, số năm KN tối thiểu, trường học, công ty từng làm).
2. semantic_search_cv — dùng khi câu hỏi MỞ, cần hiểu ngữ nghĩa (vd "ai phù
   hợp với vị trí X", so sánh ứng viên).
3. evaluate_candidate_against_jd — dùng khi cần CHẤM ĐIỂM 1 ứng viên cụ thể
   theo 1 JD.

Luôn ưu tiên filter_candidates_sql nếu câu hỏi có thể trả lời bằng tiêu chí rõ
ràng — nhanh và chính xác hơn semantic search. Trả lời bằng tiếng Việt, ngắn
gọn, dựa trên dữ liệu tool trả về — không bịa thông tin ứng viên không có
trong kết quả tool."""

_tools = [filter_candidates_sql, semantic_search_cv, evaluate_candidate_against_jd]


def build_agent_executor():
    """LangChain 1.x: create_agent() dùng LangGraph nội bộ, thay hẳn API cũ
    (AgentExecutor/create_tool_calling_agent đã bị loại bỏ khỏi LangChain 1.x).
    Trả về 1 compiled graph, invoke bằng {"messages": [...]}.
    """
    llm = ChatGoogleGenerativeAI(model=settings.GEMINI_LLM_MODEL, google_api_key=settings.GOOGLE_API_KEY)
    return create_agent(model=llm, tools=_tools, system_prompt=SYSTEM_PROMPT)
