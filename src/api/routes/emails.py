from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Query, Response
from src.api.dependencies import Token
from src.api.schemas.common import ERROR_RESPONSES
from src.api.schemas.emails import (ConfirmInvitation, CreateInvitationBatch, DispatchInvitations,
    DraftRevision, EmailFilters, SaveInvitationDraft, InvitationBatchView, InvitationBatchPage, EmailHistoryPage, EmailHistoryDetail)
from src.auth.service import auth_scope
from src.notification import invitations as service

router = APIRouter(prefix="/api/emails", tags=["emails"], responses=ERROR_RESPONSES)


def execute(token, response, fn, *args, **kwargs):
    with auth_scope(token):
        result = fn(*args, **kwargs)
    response.headers["Cache-Control"] = "private, no-store"
    return result


@router.post("/batches", response_model=InvitationBatchView)
def create_batch(body: CreateInvitationBatch, token: Token, response: Response):
    return execute(token, response, service.create_batch, **body.model_dump())


@router.get("/batches", response_model=InvitationBatchPage)
def batches(token: Token, response: Response, page: int = Query(1, ge=1, le=1000000), page_size: int = Query(20, ge=1, le=100)):
    return execute(token, response, service.list_batches, page, page_size)


@router.get("/batches/{batch_id}", response_model=InvitationBatchView)
def get_batch(batch_id: UUID, token: Token, response: Response):
    return execute(token, response, service.get_batch, str(batch_id))


@router.post("/batches/{batch_id}/dispatch", status_code=202, response_model=InvitationBatchView)
def dispatch(batch_id: UUID, body: DispatchInvitations, token: Token, response: Response):
    return execute(token, response, service.dispatch, str(batch_id), **body.model_dump())


@router.post("/batches/{batch_id}/requeue", status_code=202, response_model=InvitationBatchView)
def requeue(batch_id: UUID, body: ConfirmInvitation, token: Token, response: Response):
    return execute(token, response, service.requeue, str(batch_id))


@router.post("/drafts/{draft_id}", response_model=InvitationBatchView)
def save(draft_id: UUID, body: SaveInvitationDraft, token: Token, response: Response):
    return execute(token, response, service.save_draft, str(draft_id), **body.model_dump())


@router.post("/drafts/{draft_id}/generate", response_model=InvitationBatchView)
def generate(draft_id: UUID, body: DraftRevision, token: Token, response: Response):
    return execute(token, response, service.generate_draft, str(draft_id), **body.model_dump())


@router.post("/deliveries/{delivery_id}/retry", status_code=202, response_model=InvitationBatchView)
def retry(delivery_id: UUID, body: ConfirmInvitation, token: Token, response: Response):
    return execute(token, response, service.retry_delivery, str(delivery_id), **body.model_dump())


@router.post("/deliveries/{delivery_id}/reconcile", response_model=InvitationBatchView)
def reconcile(delivery_id: UUID, body: ConfirmInvitation, token: Token, response: Response):
    return execute(token, response, service.reconcile_delivery, str(delivery_id))


@router.get("/history", response_model=EmailHistoryPage)
def history(token: Token, response: Response, filters: Annotated[EmailFilters, Query()]):
    return execute(token, response, service.history, **filters.model_dump())


@router.get("/history/{email_id}", response_model=EmailHistoryDetail)
def detail(email_id: int, token: Token, response: Response):
    return execute(token, response, service.history_detail, email_id)
