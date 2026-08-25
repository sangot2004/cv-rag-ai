from pydantic import BaseModel, Field


class ExperienceItem(BaseModel):
    company: str = Field(description="Tên công ty")
    title: str = Field(description="Chức danh / vị trí")
    start_date: str | None = Field(default=None, description="Định dạng YYYY-MM nếu có, None nếu không rõ")
    end_date: str | None = Field(default=None, description="YYYY-MM, hoặc None nếu đang làm / không rõ")
    description: str | None = Field(default=None, description="Mô tả công việc, thành tích")


class EducationItem(BaseModel):
    school: str = Field(description="Tên trường")
    degree: str | None = Field(default=None, description="Bằng cấp, ví dụ: Cử nhân, Thạc sĩ")
    field: str | None = Field(default=None, description="Chuyên ngành")
    graduation_year: int | None = Field(default=None, description="Năm tốt nghiệp nếu có")


class CertificateItem(BaseModel):
    name: str = Field(description="Tên chứng chỉ, ví dụ: AWS Certified Solutions Architect")
    issuer: str | None = Field(default=None, description="Đơn vị cấp chứng chỉ")
    issue_date: str | None = Field(default=None, description="Ngày cấp, định dạng YYYY-MM nếu có")
    credential_id: str | None = Field(default=None, description="Mã chứng chỉ nếu CV có ghi rõ")


class ProjectItem(BaseModel):
    name: str = Field(description="Tên dự án")
    role: str | None = Field(default=None, description="Vai trò trong dự án, ví dụ: Backend Developer")
    tech_stack: list[str] = Field(default_factory=list, description="Công nghệ/ngôn ngữ dùng trong dự án")
    description: str | None = Field(
        default=None, description="Mô tả dự án, không bao gồm role/tech_stack đã tách riêng")
    start_date: str | None = Field(default=None, description="YYYY-MM nếu có")
    end_date: str | None = Field(default=None, description="YYYY-MM, None nếu đang làm/không rõ")


class CVSchema(BaseModel):
    full_name: str = Field(description="Họ tên đầy đủ ứng viên")
    email: str | None = Field(default=None)
    phone: str | None = Field(default=None)
    applied_position: str | None = Field(
        default=None, description="Vị trí ứng tuyển nếu CV có ghi rõ, hoặc suy luận từ nội dung"
    )
    total_years_experience: float | None = Field(
        default=None, description="Tổng số năm kinh nghiệm, tự tính từ các mốc thời gian experience"
    )
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certificates: list[CertificateItem] = Field(
        default_factory=list, description="Danh sách chứng chỉ, để rỗng nếu CV không đề cập")
    projects: list[ProjectItem] = Field(
        default_factory=list, description="Danh sách dự án đã làm, để rỗng nếu CV không đề cập")


class CVClassification(BaseModel):
    """Kết quả bước A5b — phân loại văn bản có phải CV không, trước khi extract đầy đủ."""

    is_cv: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
