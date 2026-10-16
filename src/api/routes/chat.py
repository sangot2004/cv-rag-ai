from uuid import UUID
from fastapi import APIRouter

from src.api.dependencies import Token
from src.api.schemas.common import ERROR_RESPONSES
from src.api.schemas.chat import AskRequest, ResumeRequest, FeedbackRequest, FeedbackResponse, ChatResponse
from src.auth.service import auth_scope
from src.chat import service

router = APIRouter(prefix="/api/conversations", tags=["chat"], responses=ERROR_RESPONSES)


@router.post("/{thread_id}/messages", response_model=ChatResponse)
def ask(thread_id: UUID, body: AskRequest, token: Token):
    with auth_scope(token):
        return service.send_message(str(thread_id), body.question)


@router.post("/{thread_id}/resume", response_model=ChatResponse)
def resume(thread_id: UUID, body: ResumeRequest, token: Token):
    edits = body.edited_criteria.model_dump(exclude_unset=True) if body.edited_criteria else None
    with auth_scope(token):
        return service.resume_message(str(thread_id), body.confirmation_id, body.confirmed, edits)


@router.post("/{thread_id}/feedback", status_code=201, response_model=FeedbackResponse)
def feedback(thread_id: UUID, body: FeedbackRequest, token: Token):
    with auth_scope(token):
        return service.submit_feedback(str(thread_id), body.message_id, body.feedback)
