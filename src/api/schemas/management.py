from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, model_validator
from src.api.schemas.common import StrictInput, UTCDateTime

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class PageFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(default=1, ge=1, le=1000000)
    page_size: int = Field(default=20, ge=1, le=100)
    q: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None


class PostingFilters(PageFilters):
    department_id: UUID | None = None


class UserFilters(PostingFilters):
    role: Literal["admin", "tester"] | None = None
    active: bool | None = None


class CreateDepartment(StrictInput):
    department_name: Name


class CreatePosting(StrictInput):
    department_id: str
    position_title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]

    @model_validator(mode="after")
    def uuid(self):
        self.department_id = str(UUID(self.department_id))
        return self


class CreateUser(StrictInput):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=100)]
    password: SecretStr = Field(min_length=12, max_length=256)
    role: Literal["admin", "tester"] = "tester"
    department_id: str | None = None

    @model_validator(mode="after")
    def department(self):
        self.username = self.username.lower()
        if self.department_id:
            self.department_id = str(UUID(self.department_id))
        if self.role == "tester" and not self.department_id:
            raise ValueError("Tester requires a department")
        return self


class UserActive(StrictInput):
    active: bool


class AssignPosting(StrictInput):
    posting_id: str | None
    expected_posting_id: str | None

    @model_validator(mode="after")
    def ids(self):
        for name in ("posting_id", "expected_posting_id"):
            value = getattr(self, name)
            if value is not None:
                setattr(self, name, str(UUID(value)))
        return self


class DepartmentView(BaseModel):
    department_id: str
    department_name: str
    posting_count: int
    cv_count: int


class PostingView(BaseModel):
    posting_id: str
    department_id: str
    department_name: str
    position_title: str
    is_active: bool
    cv_count: int
    created_at: UTCDateTime


class UserView(BaseModel):
    user_id: str
    username: str
    role: str
    department_id: str | None
    department_name: str | None
    is_active: bool
    created_at: UTCDateTime


class Page(BaseModel):
    total: int
    page: int
    page_size: int
    has_next: bool


class DepartmentPage(Page):
    items: list[DepartmentView]


class PostingPage(Page):
    items: list[PostingView]


class UserPage(Page):
    items: list[UserView]
