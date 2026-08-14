from langchain_core.tools import tool

from src.evaluation.evaluator import evaluate_candidate


@tool
def evaluate_candidate_against_jd(candidate_id: str, job_description: str) -> str:
    """Đánh giá 1 ứng viên cụ thể có phù hợp với 1 Job Description hay không.
    Dùng khi câu hỏi yêu cầu CHẤM ĐIỂM/ĐÁNH GIÁ ứng viên theo tiêu chí công
    việc, không phải chỉ tìm kiếm/liệt kê ứng viên.
    """
    result = evaluate_candidate(candidate_id, job_description)
    if result is None:
        return f"Không tìm thấy candidate_id={candidate_id}."

    criteria_lines = "\n".join(
        f"  - {c.criterion}: {c.score}/5 — {c.justification}" for c in result.criteria
    )
    return (
        f"Điểm tổng: {result.overall_score:.1f}/5\n"
        f"Chi tiết:\n{criteria_lines}\n"
        f"Điểm mạnh: {', '.join(result.strengths)}\n"
        f"Cần lưu ý: {', '.join(result.concerns)}\n"
        f"Tóm tắt: {result.summary}"
    )
