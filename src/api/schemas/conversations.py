from pydantic import BaseModel
from src.api.schemas.common import StrictInput, UTCDateTime


class CreateConversationRequest(StrictInput):
    pass


class ConversationResponse(BaseModel):
    thread_id: str
    title: str
    created_at: UTCDateTime
    updated_at: UTCDateTime


class ConversationList(BaseModel):
    items: list[ConversationResponse]
    limit: int
