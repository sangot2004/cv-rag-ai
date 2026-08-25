from langchain_core.tools import tool

from src.retrieval.sql_query_tool import get_candidate_full_profile


@tool
def get_candidate_detail(candidate_id: str) -> str:
    """Lấy đầy đủ thông tin 1 ứng viên theo (skills, kinh nghiệm, học vấn...)
    Dùng khi muốn hỏi chi tiết về 1 ứng viên cụ thể"""
    profile = get_candidate_full_profile(candidate_id)
    if profile is None:
        return f"không tìm thấy candidate_id={candidate_id}"
    return str(profile)
