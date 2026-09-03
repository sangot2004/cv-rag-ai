from langchain_core.tools import tool

from src.retrieval.sql_query_tool import get_multiple_candidates_profile


@tool
def compare_candidates(candidate_ids: list[str]) -> str:
    """Lấy dữ liệu đầy đủ của NHIỀU ứng viên cùng lúc để so sánh với nhau
    (kỹ năng, kinh nghiệm, học vấn, dự án). Dùng khi câu hỏi yêu cầu SO SÁNH
    2 ứng viên trở lên — bạn (Agent) tự phân tích/so sánh dựa trên dữ liệu
    tool này trả về, tool chỉ cung cấp dữ liệu thô, không tự chấm điểm.
    """
    profiles = get_multiple_candidates_profile(candidate_ids)
    if not profiles:
        return "Không tìm thấy ứng viên nào trong danh sách candidates_ids đã cho."
    return str(profiles)
