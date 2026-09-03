from pydantic import BaseModel, Field


class JDSchema(BaseModel):
    position_title: str = Field(description="Tên vị trí tuyển dụng")
    required_skills: list[str] = Field(
        default_factory=list, description="Kỹ năng bắt buộc/ quan trọng nhất theo JD"
    )
    min_years_experience: float | None = Field(
        default=None, description="Số năm kinh nghiệm tối thiểu yêu cầu, None nếu JD không ghi rõ"
    )
    preferred_education: str | None = Field(
        default=None, description="Yêu cầu học vấn nếu có, vd 'Cử nhân CNTT trở lên'"
    )
    raw_text: str = Field(description="Toàn bộ text JD gốc, giữ nguyên để dùng cho semantic search/prompt")
