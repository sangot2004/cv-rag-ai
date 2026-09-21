import logging

from langchain_core.tools import tool
from langgraph.types import interrupt

from src.ingestion.extraction.llm_extractor import extract_jd_data
from src.retrieval.candidate_ranking import rank_candidates_for_jd

logger = logging.getLogger(__name__)


@tool
def find_top_candidates_for_jd(jd_text: str, top_k: int = 5) -> str:
    """Cho 1 Job Description (JD) dạng text, tìm ra TOP K ứng viên phù hợp
    nhất trong toàn bộ hệ thống, có chấm điểm chi tiết theo rubric. Dùng khi
    câu hỏi đưa vào 1 JD và hỏi "ai phù hợp nhất", "tìm ứng viên cho vị trí
    này" — KHÁC với evaluate_candidate_against_jd (tool đó chỉ chấm 1 người
    đã biết trước candidate_id).

    QUAN TRỌNG — Double Opt-in: tool này DỪNG LẠI (chặn kỹ thuật, không thể
    bỏ qua) để chờ HR xác nhận tiêu chí đã trích xuất, TRƯỚC KHI chạy bước
    xếp hạng tốn kém (K+1 lời gọi Gemini). Không cần tự hỏi lại HR trong
    câu trả lời trước khi gọi tool — cơ chế xác nhận đã nằm SẴN bên trong.
    """
    jd = extract_jd_data(jd_text)

    confirmation = interrupt(
        {
            "type": "confirm_jd_criteria",
            "position_title": jd.position_title,
            "required_skills": jd.required_skills,
            "min_years_experience": jd.min_years_experience,
            "preferred_education": jd.preferred_education,
            "top_k": top_k,
        }
    )

    if not confirmation.get("confirmed", False):
        logger.info("find_top_candidates_for_jd: HR huỷ, không chạy ranking")
        return "HR đã huỷ yêu cầu tìm kiếm này, không có gì được xử lý thêm."

    edited = confirmation.get("edited_criteria")
    if edited:
        jd.position_title = edited.get("position_title", jd.position_title)
        jd.required_skills = edited.get("required_skills", jd.required_skills)
        jd.min_years_experience = edited.get("min_years_experience", jd.min_years_experience)
        top_k = edited.get("top_k", top_k)

    results = rank_candidates_for_jd(jd, top_k=top_k)

    if not results:
        return f"Không tìm thấy ứng viên nào phù hợp với JD vị trí '{jd.position_title}'."

    lines = [f"Top {len(results)} ứng viên phù hợp nhất với vị trí '{jd.position_title}':"]
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. candidate_id={r['candidate_id']} - điểm: {r['overall_score']:.1f}/5 - {r['summary']}"
        )
    return "\n".join(lines)
