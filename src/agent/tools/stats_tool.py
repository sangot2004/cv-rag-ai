from langchain_core.tools import tool

from src.retrieval.sql_query_tool import count_candidate_stats


@tool
def count_candidates(skills: list[str] | None = None, min_years_experience: float | None = None) -> str:
    """Đếm SỐ LƯỢNG ứng viên khớp tiêu chí — trả về 1 con số, khác với
    filter_candidates_sql (trả danh sách chi tiết từng người). Dùng cho câu
    hỏi dạng "có bao nhiêu ứng viên...", "tổng số ứng viên biết Python là
    bao nhiêu".
    """
    result = count_candidate_stats(skills=skills, min_years_experience=min_years_experience)
    return f"Có {result['count']} ứng viên khớp tiêu chí"
