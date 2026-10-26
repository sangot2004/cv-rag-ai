from typing import Annotated, Literal
from pydantic import BaseModel, Field, field_validator

from src.api.schemas.common import StrictInput
from src.chat.criteria import Criteria, CriteriaEdits
from src.chat.candidate_results import ResultGroup


class AskRequest(StrictInput):
    question: str = Field(min_length=1, max_length=20000)

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Question cannot be blank")
        return value


class ResumeRequest(StrictInput):
    confirmation_id: str = Field(min_length=1, max_length=200)
    confirmed: bool
    edited_criteria: CriteriaEdits | None = None


class FeedbackRequest(StrictInput):
    message_id: str = Field(min_length=1, max_length=200)
    feedback: Literal["up", "down"]


class FeedbackResponse(BaseModel):
    message_id: str
    feedback: Literal["up", "down"]


class Message(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    candidate_results: list[ResultGroup] = Field(default_factory=list)


class PendingConfirmation(BaseModel):
    confirmation_id: str
    type: Literal["confirm_jd_criteria"]
    criteria: Criteria


class HistoryResponse(BaseModel):
    thread_id: str
    messages: list[Message]
    pending_confirmations: list[PendingConfirmation]
    execution_status: Literal["idle", "running", "awaiting_confirmation", "failed", "interrupted"]


class AnswerResponse(BaseModel):
    type: Literal["answer"]
    thread_id: str
    message: Message


class ConfirmationResponse(BaseModel):
    type: Literal["confirmation_required"]
    thread_id: str
    pending_confirmations: list[PendingConfirmation]


class CancelledResponse(BaseModel):
    type: Literal["cancelled"]
    thread_id: str
    message: None = None


ChatResponse = Annotated[AnswerResponse | ConfirmationResponse | CancelledResponse, Field(discriminator="type")]
