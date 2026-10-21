from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from src.api.schemas.common import StrictInput

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Subject = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500, pattern=r"^[^\r\n]+$")]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=15000)]


class CreateInvitationBatch(StrictInput):
    request_id: str = Field(pattern=r"^[a-fA-F0-9-]{36}$")
    kind: Literal["single", "bulk"]
    candidate_ids: list[str] = Field(min_length=1, max_length=20)
    name: Text = Field(max_length=255)
    position: Text = Field(max_length=255)
    interview_details: Text = Field(max_length=8000)

    @model_validator(mode="after")
    def valid_candidates(self):
        self.request_id = str(UUID(self.request_id))
        self.candidate_ids = [str(UUID(value)) for value in self.candidate_ids]
        if len(set(self.candidate_ids)) != len(self.candidate_ids) or (self.kind == "single" and len(self.candidate_ids) != 1):
            raise ValueError("Invalid candidate selection")
        return self


class DraftRevision(StrictInput):
    expected_revision: int = Field(ge=1)


class SaveInvitationDraft(DraftRevision):
    subject: Subject
    body: Body


class ApprovedDraft(StrictInput):
    draft_id: str
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def identifier(self):
        self.draft_id = str(UUID(self.draft_id))
        return self


class ConfirmInvitation(StrictInput):
    confirmed: bool
    allow_previous: bool = False

    @model_validator(mode="after")
    def confirmation(self):
        if self.confirmed is not True:
            raise ValueError("Explicit approval required")
        return self


class DispatchInvitations(ConfirmInvitation):
    drafts: list[ApprovedDraft] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_drafts(self):
        if len({d.draft_id for d in self.drafts}) != len(self.drafts):
            raise ValueError("Duplicate draft")
        return self


class EmailFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(default=1, ge=1, le=1000000)
    page_size: int = Field(default=20, ge=1, le=100)
    q: str | None = Field(default=None, max_length=200)
    status: Literal["queued", "sending", "success", "failed", "unknown"] | None = None
    candidate_id: UUID | None = None
    batch_id: UUID | None = None
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode="after")
    def date_order(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("Invalid date range")
        return self


from src.api.schemas.common import UTCDateTime


class InvitationDraftView(BaseModel):
    draft_id: str
    candidate_id: str
    full_name: str
    recipient_email: str | None
    subject: str
    body: str
    revision: int
    error_code: str | None
    is_generating: bool
    ready: bool
    previously_sent: bool


class InvitationDeliveryView(BaseModel):
    delivery_id: str
    draft_id: str
    candidate_id: str
    full_name: str
    recipient_email: str
    subject: str
    status: str
    attempts: int
    error_code: str | None
    gmail_message_id: str | None
    started_at: UTCDateTime | None
    finished_at: UTCDateTime | None


class InvitationBatchSummary(BaseModel):
    batch_id: str
    kind: str
    name: str
    position: str
    interview_details: str
    status: str
    total: int
    counts: dict[str, int]
    dispatch_error: str | None
    created_at: UTCDateTime


class InvitationBatchView(InvitationBatchSummary):
    drafts: list[InvitationDraftView]
    deliveries: list[InvitationDeliveryView]


class InvitationBatchPage(BaseModel):
    items: list[InvitationBatchSummary]
    total: int
    page: int
    page_size: int
    has_next: bool


class EmailHistoryItem(BaseModel):
    id: int
    candidate_id: str
    full_name: str
    recipient_email: str
    subject: str
    status: str
    batch_id: str | None
    delivery_id: str | None
    sent_at: UTCDateTime
    gmail_message_id: str | None
    error_code: str | None


class EmailHistoryDetail(EmailHistoryItem):
    body: str


class EmailHistoryPage(BaseModel):
    items: list[EmailHistoryItem]
    total: int
    page: int
    page_size: int
    has_next: bool
