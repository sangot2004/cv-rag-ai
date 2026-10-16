from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def utc_datetime(value):
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


UTCDateTime = Annotated[datetime, BeforeValidator(utc_datetime)]


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


ERROR_RESPONSES = {
    status: {"model": ErrorResponse}
    for status in (401, 403, 404, 409, 422, 500, 503, 504)
}
