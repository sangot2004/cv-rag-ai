from pydantic import BaseModel, Field


class CriterionScore(BaseModel):
    criterion: str = Field(description="Tên tiêu chí đánh giá")
    score: int = Field(description="Điểm 1-5, 1=rất không phù hợp, 5=rất phù hợp")
    justification: str = Field(description="Lý do ngắn gọn cho điểm số này, dựa trên dữ liệu cv cụ thể")


class EvaluationResult(BaseModel):
    candidate_id: str
    overall_score: float = Field(description="Điểm trung bình các tiêu chí, 1.0-5.0")
    criteria: list[CriterionScore]
    strengths: list[str] = Field(description="Điểm mạnh nổi bật, tối đa 3 gạch đầu dòng")
    concerns: list[str] = Field(description="Điểm cần lưu ý/thiếu sót, tối đa 3 gạch đầu dòng")
    summary: str = Field(description="Tóm tắt 2-3 câu, dùng để gửi Slack")


# Rubric cố định — LLM chấm theo đúng các tiêu chí này, không tự bịa thêm
# tiêu chí khác, để kết quả nhất quán giữa các lần chấm và giữa các candidate.
DEFAULT_CRITERIA = [
    "Kỹ năng chuyên môn khớp với JD",
    "Số năm kinh nghiệm phù hợp với yêu cầu vị trí",
    "Kinh nghiệm thực tế liên quan (dự án/công ty từng làm)",
    "Học vấn/chứng chỉ liên quan",
]
