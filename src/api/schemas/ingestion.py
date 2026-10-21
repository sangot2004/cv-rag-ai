from typing import Literal
from pydantic import BaseModel, field_validator
from src.api.schemas.management import Page, PageFilters
from src.api.schemas.common import StrictInput, UTCDateTime


class JobFilters(PageFilters):
    status: Literal["pending", "processing", "failed", "dlq", "rejected", "indexed"] | None = None
    source_type: Literal["web_upload", "email"] | None = None


class RetryJob(StrictInput):
    confirmed: bool

    @field_validator("confirmed")
    @classmethod
    def confirmation(cls, value):
        if value is not True:
            raise ValueError("Confirmation is required")
        return value


class JobView(BaseModel):
    job_id: str
    original_filename: str
    source_type: str
    status: str
    attempts: int
    max_attempts: int
    error_code: str | None
    dispatch_error: str | None
    created_at: UTCDateTime
    updated_at: UTCDateTime
    started_at: UTCDateTime | None
    candidate_id: str | None
    candidate_name: str | None
    posting_id: str | None
    position_title: str | None
    department_name: str | None
    can_retry: bool


class JobPage(Page):
    items: list[JobView]


class UploadCapabilities(BaseModel):
    extensions: list[str]
    min_bytes: int
    max_bytes: int
    max_pages: int
    filename_pattern: str
    filename_example: str
