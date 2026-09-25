from langchain_core.tools import tool

from src.interfaces.interview_interface import generate_questions_for_candidate


@tool
def generate_interview_questions_for_candidate(candidate_id: str, max_questions: int = 8) -> str:
    """Sinh câu hỏi phỏng vấn cho 1 ứng viên cụ thể, dựa CHỈ trên nội dung
    CV thật của họ (mỗi câu kèm trích dẫn từ CV làm bằng chứng, đã được hệ
    thống tự kiểm tra không bịa đặt). Dùng khi HR yêu cầu "sinh câu hỏi
    phỏng vấn cho ứng viên X", "chuẩn bị câu hỏi PV dựa trên CV này".

    Gọi lại tool này sẽ THAY THẾ toàn bộ câu hỏi cũ đã sinh trước đó cho
    đúng candidate_id này (không cộng dồn).
    """
    result = generate_questions_for_candidate(candidate_id, max_questions=max_questions)

    if result["error"]:
        return f"Không sinh được câu hỏi: {result['error']}"

    if not result["questions"]:
        return "CV của ứng viên này chưa đủ thông tin cụ thể để sinh câu hỏi đáng tin cậy."

    lines = [f"Đã sinh {len(result['questions'])} câu hỏi phỏng vấn: "]
    for q in result["questions"]:
        lines.append(f"\n[{q['category']}] {q['question']}")
        lines.append(f"  (Dựa trên mục '{q['cv_section']}': \"{q['evidence_quote'][:100]}\")")

    return "\n".join(lines)
