from enum import Enum

from pydantic import BaseModel, Field


class InterviewCategory(str, Enum):
    TECHNICAL = "Technical"
    SYSTEM_DESIGN = "System Design"
    SOFT_SKILL = "Soft Skill"


class InterviewQuestion(BaseModel):
    question: str = Field(description="Câu hỏi phỏng vấn")
    category: InterviewCategory = Field(description="Phân loại câu hỏi")
    cv_section: str = Field(description="Tên section trong CV chứa thông tin làm cơ sở")
    evidence_quote: str = Field(
        description="Trích dẫn NGUYÊN VĂN từ CV dùng làm cơ sở đặt câu hỏi - phải xuất hiện đúng trong CV gốc"
    )


class QuestionList(BaseModel):
    questions: list[InterviewQuestion]
