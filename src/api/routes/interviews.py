from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from src.api.dependencies import Token
from src.api.schemas.common import ERROR_RESPONSES
from src.api.schemas.interviews import GenerateInterviewQuestions, InterviewQuestions
from src.auth.service import auth_scope
from src.interview import service

router = APIRouter(prefix="/api/candidates/{candidate_id}/interview-questions", tags=["interviews"], responses=ERROR_RESPONSES)


@router.get("", response_model=InterviewQuestions)
def get_questions(candidate_id: UUID, token: Token, response: Response):
    with auth_scope(token):
        result = service.get_questions(str(candidate_id))
    response.headers["Cache-Control"] = "private, no-store"
    return result


@router.post("/generate", response_model=InterviewQuestions)
def generate_questions(candidate_id: UUID, token: Token, body: GenerateInterviewQuestions, response: Response):
    with auth_scope(token):
        result = service.generate_questions(str(candidate_id), **body.model_dump())
    response.headers["Cache-Control"] = "private, no-store"
    return result


@router.delete("", response_model=InterviewQuestions)
def delete_questions(candidate_id: UUID, token: Token, response: Response,
                     expected_revision: Annotated[str, Query(pattern=r"^[a-f0-9]{64}$")]):
    with auth_scope(token):
        result = service.delete_questions(str(candidate_id), expected_revision=expected_revision)
    response.headers["Cache-Control"] = "private, no-store"
    return result
