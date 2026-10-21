from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from src.api.dependencies import Token
from src.api.schemas.candidates import CandidateDetail, CandidateFilters, CandidateList
from src.api.schemas.common import ERROR_RESPONSES
from src.auth.service import auth_scope
from src.candidates import service
from src.candidates.photos import get_candidate_photo
from src.api.schemas.management import AssignPosting
from src.management.service import assign_posting

router = APIRouter(prefix="/api/candidates", tags=["candidates"], responses=ERROR_RESPONSES)


@router.post("/{candidate_id}/posting")
def assign(candidate_id: UUID, body: AssignPosting, token: Token, response: Response):
    with auth_scope(token):
        result = assign_posting(str(candidate_id), **body.model_dump())
    response.headers["Cache-Control"] = "private, no-store"
    return result


@router.get("", response_model=CandidateList)
def list_candidates(token: Token, response: Response, filters: Annotated[CandidateFilters, Query()]):
    with auth_scope(token):
        result = service.list_candidates(**filters.model_dump(mode="json"))
    response.headers["Cache-Control"] = "private, no-store"
    return result


@router.get("/{candidate_id}", response_model=CandidateDetail)
def candidate_detail(candidate_id: UUID, token: Token, response: Response):
    with auth_scope(token):
        result = service.get_candidate(str(candidate_id))
    response.headers["Cache-Control"] = "private, no-store"
    return result


@router.get("/{candidate_id}/photo", response_class=Response,
            responses={200: {"content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}}}})
def candidate_photo(candidate_id: UUID, token: Token):
    with auth_scope(token):
        data, media_type = get_candidate_photo(str(candidate_id))
    return Response(data, media_type=media_type,
                    headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
