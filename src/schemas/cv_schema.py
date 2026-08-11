from pydantic import BaseModel, Field


class ExperienceItem(BaseModel):
    company: str = Field(description="Tên công ty")
    title: str = Field(description="Chức danh / vị trí")
    start_date: str | None = Field(default=None, description="Định dạng YYYY-MM nếu có, None nếu không rõ")
    end_date: str | None = Field(default=None, description="YYYY-MM, hoặc None nếu đang làm / không rõ")
    description: str | None = Field(default=None, description="Mô tả công việc, thành tích")


class EducationItem(BaseModel):
    school: str = Field(description="Tên trường")
    degree: str | None = Field(default=None, description=" Bằng cấp, ví dụ: Cử nhân, Kỹ sư")
    field: str | None = Field(default=None, description="Chuyên ngành")
    graduation_year: int | None = Field(default=None, description="Năm tốt nghiệp nếu có")


class CVSchema(BaseModel):
    full_name: str = Field(description="Họ tên đầy đủ ứng viên")
    email: str | None = Field(default=None)
    phone: str | None = Field(default=None)
    applied_position: str | None = Field(
        default=None, description="Vị trí ứng tuyển nếu cv ghi rõ, hoặc suy luận từ nội dung"
    )
    total_years_experience: float | None = Field(
        default=None, description="Tổng số năm kinh nghiệm, tự tính từ các mốc thời gian experience"
    )
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)


class CVClassification(BaseModel):
    """Kết quả: phân loại văn bản có phải cv ko, trước khi extract đầy đủ"""
    is_cv: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
