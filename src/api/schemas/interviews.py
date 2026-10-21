from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from src.api.schemas.common import StrictInput
from src.schemas.interview_question_schema import InterviewCategory

Revision = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class GenerateInterviewQuestions(StrictInput):
    max_questions: int = Field(default=8, ge=3, le=15)
    expected_revision: Revision
    replace_existing: bool = False


class SavedInterviewQuestion(BaseModel):
    id: int
    question: str
    category: InterviewCategory
    cv_section: str
    evidence_quote: str


class InterviewQuestions(BaseModel):
    candidate_id: str
    items: list[SavedInterviewQuestion]
    revision: Revision
    has_cv: bool
    is_generating: bool
