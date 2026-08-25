from langchain_core.tools import tool

from src.retrieval.sql_query_tool import get_multiple_candidates_profile


@tool
def compare_candidates(candidate_ids: list[str]) -> str:
    """Lấy dữ liệu đầy đủ của nhiều ứng viên cùng lúc để so sánh"""
    profiles = get_multiple_candidates_profile(candidate_ids)
    if not profiles:
        return "Không tìm thấy ứng viên nào trong danh sách candidates_ids đã cho."
    return str(profiles)
