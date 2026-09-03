from langchain_core.tools import tool

from src.ingestion.extraction.llm_extractor import extract_jd_data
from src.retrieval.candidate_ranking import rank_candidates_for_jd


@tool
def find_top_candidates_for_jd(jd_text: str, top_k: int = 5) -> str:
    """Cho 1 Job Description (JD) dạng text, tìm ra TOP K ứng viên phù hợp
    nhất trong toàn bộ hệ thống, có chấm điểm chi tiết theo rubric. Dùng khi
    câu hỏi đưa vào 1 JD và hỏi "ai phù hợp nhất", "tìm ứng viên cho vị trí
    này" — KHÁC với evaluate_candidate_against_jd (tool đó chỉ chấm 1 người
    đã biết trước candidate_id).
    """
    jd = extract_jd_data(jd_text)
    results = rank_candidates_for_jd(jd, top_k=top_k)

    if not results:
        return f"Không tìm thấy ứng viên nào phù hợp với JD vị trí ''{jd.position_title}."

    lines = [f"Top {len(results)} ứng viên phù hợp nhất với vị trí '{jd.position_title}':"]
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. candidate_id={r['candidate_id']} - điểm: {r['overall_score']:.1f}/5 - {r['summary']}"
        )
    return "\n".join(lines)
