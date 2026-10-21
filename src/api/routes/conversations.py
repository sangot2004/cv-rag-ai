from typing import Annotated
from fastapi import APIRouter, Body, Query, Response

from src.api.dependencies import Token
from src.api.schemas.common import ERROR_RESPONSES
from src.api.schemas.conversations import CreateConversationRequest, ConversationResponse, ConversationList
from src.api.schemas.chat import HistoryResponse
from src.api.schemas.identifiers import ConversationId
from src.auth.service import auth_scope
from src.chat import conversation_store as store
from src.chat.service import history

router = APIRouter(prefix="/api/conversations", tags=["conversations"], responses=ERROR_RESPONSES)


@router.post("", status_code=201, response_model=ConversationResponse)
def create(token: Token, body: Annotated[CreateConversationRequest, Body()] = CreateConversationRequest()):
    with auth_scope(token):
        return store.conversation_metadata(store.create_conversation())


@router.get("", response_model=ConversationList)
def list_owned(token: Token, limit: Annotated[int, Query(ge=1, le=50)] = 50):
    with auth_scope(token):
        return {"items": store.list_conversations(limit), "limit": limit}


@router.get("/{thread_id}/messages", response_model=HistoryResponse)
def messages(thread_id: ConversationId, token: Token):
    with auth_scope(token):
        return history(thread_id)


@router.delete("/{thread_id}", status_code=204, response_class=Response)
def delete(thread_id: ConversationId, token: Token):
    with auth_scope(token):
        store.delete_conversation(thread_id)
    return Response(status_code=204)
