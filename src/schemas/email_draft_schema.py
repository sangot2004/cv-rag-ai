from pydantic import BaseModel, Field


class EmailDraft(BaseModel):
    subject: str = Field(description="Tiêu đề email, ngắn gọn, chuyên nghiệp")
    body: str = Field(
        description="Nội dung email đầy đủ, lịch sự, đúng thông tin đã cho - không tự bịa thêm chi tiết (thời gian/địa điểm) nếu không được cung cấp")
