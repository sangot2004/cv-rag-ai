from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}
