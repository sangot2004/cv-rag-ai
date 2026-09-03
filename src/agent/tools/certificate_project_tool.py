from langchain_core.tools import tool

from src.retrieval.sql_query_tool import search_by_certificate, search_by_project_tech


@tool
def find_candidates_by_certificate(certificate_name: str) -> str:
    """Tìm ứng viên có chứng chỉ cụ thể (vd "AWS Certified", "PMP",
    "IELTS..."). Dùng khi câu hỏi hỏi về chứng chỉ, KHÔNG dùng cho kỹ năng nói
    chung (kỹ năng dùng filter_candidates_sql).
    """
    results = search_by_certificate(certificate_name)
    if not results:
        return f"Không tìm thấy ứng viên nào có chứng chỉ khớp '{certificate_name}'."
    lines = [f"- {r['full_name']} ({r['candidate_id']})" for r in results]
    return "\n".join(lines)


@tool
def find_candidates_by_project_tech(tech: str) -> str:
    """Tìm ứng viên từng làm DỰ ÁN có dùng công nghệ cụ thể (vd "React",
    "Kubernetes"). Khác filter_candidates_sql (đó là kỹ năng khai báo chung,
    còn đây là công nghệ thực tế dùng trong 1 dự án cụ thể — cụ thể và đáng
    tin hơn khi câu hỏi nhấn mạnh "đã từng làm dự án với...").
    """
    results = search_by_project_tech(tech)
    if not results:
        return f"Không tìm thấy ứng viên nào có dự án dùng công nghệ '{tech}'."
    lines = [f"- {r['full_name']} ({r['candidate_id']})" for r in results]
    return "\n".join(lines)
