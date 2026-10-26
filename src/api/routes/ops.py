from typing import Annotated
from fastapi import APIRouter, Query, Response
from src.api.dependencies import Token
from src.api.execution import execute
from src.api.schemas.common import ERROR_RESPONSES
from src.api.schemas.ops import OpsDashboard, OpsFilters
from src.ops.monitoring import dashboard

router = APIRouter(prefix="/api/ops", tags=["ops"], responses=ERROR_RESPONSES)


@router.get("/dashboard", response_model=OpsDashboard)
def monitoring(token: Token, response: Response, filters: Annotated[OpsFilters, Query()]):
    return execute(token, response, dashboard, **filters.model_dump())

from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from src.ops import workflow


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    extraction_model: str | None = Field(None, min_length=1, max_length=150)
    extraction_prompt_version: str = Field(pattern=r"^[0-9a-f]{8,40}$")
    cache_enabled: bool
    retrieval_multiplier: int = Field(ge=2, le=8)


class Confirm(BaseModel):
    confirmed: Literal[True]


class ExperimentInput(Confirm):
    dataset: str = Field(min_length=1, max_length=200, pattern=r".*\S.*")


@router.get("/optimization")
def optimization(token: Token, response: Response):
    return execute(token, response, workflow.overview)


@router.post("/optimization", status_code=201)
def proposal(body: Settings, token: Token, response: Response):
    return execute(token, response, workflow.create, body.model_dump())


@router.post("/optimization/analyze")
def analyze(body: Confirm, token: Token, response: Response):
    from src.ops.optimization import analyze_usage
    return execute(token, response, analyze_usage)


@router.post("/optimization/{identifier}/experiment", status_code=202)
def experiment(identifier: UUID, body: ExperimentInput, token: Token, response: Response):
    return execute(token, response, workflow.enqueue, str(identifier), body.dataset)


@router.post("/optimization/{identifier}/approve")
def approve(identifier: UUID, body: Confirm, token: Token, response: Response):
    return execute(token, response, workflow.activate, str(identifier))


@router.post("/optimization/{identifier}/rollback")
def rollback(identifier: UUID, body: Confirm, token: Token, response: Response):
    return execute(token, response, workflow.activate, str(identifier), rollback=True)


@router.post("/experiments/{identifier}/recover")
def recover(identifier: UUID, body: Confirm, token: Token, response: Response):
    return execute(token, response, workflow.recover, str(identifier))


@router.post("/optimization/defaults")
def defaults(body: Confirm, token: Token, response: Response):
    return execute(token, response, workflow.activate, None, rollback=True)
