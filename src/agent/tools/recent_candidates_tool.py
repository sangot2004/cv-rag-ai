from langchain_core.tools import tool

from src.retrieval.sql_query_tool import list_recent_candidates


@tool
def list_recent_cvs(limit: int = 5) -> str:
    """Liệt kê các cv mới nộp gần nhất"""
    results = list_recent_candidates(limit=limit)
    if not results:
        return "Chưa có ứng viên nào trong hệ thống."
    lines = [
        f"- {r['full_name']} - ứng tuyển {r['applied_position']} ({r['created_at']})"
        for r in results
    ]
    return "\n".join(lines)
