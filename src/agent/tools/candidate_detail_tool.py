from langchain_core.tools import tool

from src.retrieval.sql_query_tool import get_candidate_full_profile


@tool
def get_candidate_detail(candidate_id: str) -> str:
    """Lấy đầy đủ thông tin 1 ứng viên cụ thể theo candidate_id (skills,
    kinh nghiệm, học vấn, chứng chỉ, dự án đã làm). Dùng khi câu hỏi hỏi
    chi tiết về 1 người cụ thể đã biết candidate_id (thường lấy từ kết quả
    tool tìm kiếm trước đó trong cùng hội thoại).
    """
    profile = get_candidate_full_profile(candidate_id)
    if profile is None:
        return f"không tìm thấy candidate_id={candidate_id}"
    return str(profile)
