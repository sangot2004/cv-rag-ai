from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from src.api.schemas.common import UTCDateTime


SearchText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
SkillText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
PositionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class CandidateFilters(BaseModel):
    # Query values arrive as strings; parse numbers/UUIDs while rejecting extra
    # fields. JSON request bodies elsewhere retain StrictInput's strict types.
    model_config = ConfigDict(extra="forbid")
    page: int = Field(default=1, ge=1, le=1_000_000)
    page_size: int = Field(default=20, ge=1, le=100)
    q: SearchText | None = None
    position: PositionText | None = None
    skills: list[SkillText] = Field(default_factory=list, max_length=20)
    department_id: UUID | None = None
    posting_id: UUID | None = None
    min_years_experience: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_years_experience: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    sort: Literal["newest", "oldest", "name_asc", "experience_desc"] = "newest"

    @model_validator(mode="after")
    def ordered_experience_range(self):
        if (self.min_years_experience is not None and self.max_years_experience is not None
                and self.min_years_experience > self.max_years_experience):
            raise ValueError("Minimum experience cannot exceed maximum experience")
        return self


class CandidateDepartment(BaseModel):
    department_id: str
    department_name: str


class CandidatePosting(BaseModel):
    posting_id: str
    position_title: str
    is_active: bool
    department: CandidateDepartment


class CandidateSummary(BaseModel):
    candidate_id: str
    full_name: str
    email: str | None
    has_photo: bool
    applied_position: str | None
    total_years_experience: float | None
    skills: list[str]
    posting: CandidatePosting | None
    created_at: UTCDateTime
    updated_at: UTCDateTime


class CandidateList(BaseModel):
    items: list[CandidateSummary]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool


class Experience(BaseModel):
    company: str | None
    title: str | None
    start_date: date | None
    end_date: date | None
    description: str | None


class Education(BaseModel):
    school: str | None
    degree: str | None
    field: str | None
    graduation_year: int | None


class Certificate(BaseModel):
    name: str
    issuer: str | None
    issue_date: date | None
    credential_id: str | None


class Project(BaseModel):
    name: str
    role: str | None
    tech_stack: list[str]
    description: str | None
    start_date: date | None
    end_date: date | None


class CandidateDetail(CandidateSummary):
    phone: str | None
    raw_text: str | None
    experience: list[Experience]
    education: list[Education]
    certificates: list[Certificate]
    projects: list[Project]
