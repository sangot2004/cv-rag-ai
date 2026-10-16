"""Validated criteria shared by API, Streamlit and the confirmation tool."""
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CriteriaEdits(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    position_title: str | None = Field(default=None, min_length=1, max_length=500)
    required_skills: list[str] | None = Field(default=None, max_length=100)
    min_years_experience: float | None = Field(default=None, ge=0)
    preferred_education: str | None = Field(default=None, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=10)

    @field_validator("position_title", "required_skills", "top_k", mode="before")
    @classmethod
    def non_nullable_if_present(cls, value):
        if value is None:
            raise ValueError("Field cannot be null")
        return value

    @field_validator("position_title")
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Title cannot be blank")
        return value

    @field_validator("required_skills")
    @classmethod
    def valid_skills(cls, values):
        if any(not value.strip() or len(value) > 200 for value in values):
            raise ValueError("Skills must contain 1–200 characters")
        return values


class Criteria(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    position_title: str = Field(min_length=1, max_length=500)
    required_skills: list[str] = Field(max_length=100)
    min_years_experience: float | None = Field(ge=0)
    preferred_education: str | None
    top_k: int = Field(ge=1, le=10)
