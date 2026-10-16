from typing import Literal
from pydantic import BaseModel, Field, SecretStr

from src.api.schemas.common import StrictInput, UTCDateTime


class LoginRequest(StrictInput):
    username: str = Field(min_length=1, max_length=100)
    password: SecretStr = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    user_id: str
    username: str
    role: Literal["admin", "tester"]
    department_id: str | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: UTCDateTime
    expires_in: int
    user: UserResponse
