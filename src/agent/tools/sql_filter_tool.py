from langchain_core.tools import tool

from src.retrieval.sql_query_tool import search_candidates_sql


@tool
def filter_candidates_sql(
    skills: list[str] | None = None,
    min_years_experience: float | None = None,
    school: str | None = None,
    company: str | None = None,
) -> str:
    """Lọc ứng viên theo tiêu chí CHÍNH XÁC, có cấu trúc rõ ràng. Dùng khi câu
    hỏi có điều kiện cụ thể: kỹ năng cần có (vd "biết Python và SQL"), số năm
    kinh nghiệm tối thiểu (vd "trên 3 năm"), từng học ở trường nào, từng làm
    ở công ty nào. Nhanh và chính xác hơn semantic_search_cv cho loại câu hỏi
    này — KHÔNG dùng semantic_search_cv nếu câu hỏi có thể trả lời bằng tool này.
    """
    results = search_candidates_sql(
        skills=skills,
        min_years_experience=min_years_experience,
        school=school,
        company=company,
    )

    if not results:
        return "Không tìm thấy ứng viên nào khớp tiêu chí."

    lines = [
        f"- {r['full_name']} ({r['candidate_id']}): {r['total_years_experience']} năm KN, "
        f"ứng tuyển {r['applied_position']}"
        for r in results
    ]
    return "\n".join(lines)
