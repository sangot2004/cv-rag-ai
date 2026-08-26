from langchain_core.tools import tool

from src.retrieval.sql_query_tool import search_by_certificate, search_by_project_tech


@tool
def find_candidates_by_certificate(certificate_name: str) -> str:
    """tìm ứng viên có chứng chỉ cụ thể"""
    results = search_by_certificate(certificate_name)
    if not results:
        return f"Không tìm thấy ứng viên nào có chứng chỉ khớp '{certificate_name}'."
    lines = [f"- {r['full_name']} ({r['candidate_id']})" for r in results]
    return "\n".join(lines)


@tool
def find_candidates_by_project_tech(tech: str) -> str:
    """tìm ứng viên làm dự án có dùng công nghệ cụ thể"""
    results = search_by_project_tech(tech)
    if not results:
        return f"Không tìm thấy ứng viên nào có dự án dùng công nghệ '{tech}'."
    lines = [f"- {r['full_name']} ({r['candidate_id']})" for r in results]
    return "\n".join(lines)
