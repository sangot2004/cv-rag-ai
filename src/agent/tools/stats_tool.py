from langchain_core.tools import tool

from src.retrieval.sql_query_tool import count_candidate_stats


@tool
def count_candidates(skills: list[str] | None = None, min_years_experience: float | None = None) -> str:
    """Đếm số lượng ứng viên khớp tiêu chí"""
    result = count_candidate_stats(skills=skills, min_years_experience=min_years_experience)
    return f"Có {result['count']} ứng viên khớp tiêu chí"
