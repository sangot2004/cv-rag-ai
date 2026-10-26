from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class OpsFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days: Literal[1, 7, 30] = 7
    module: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=150)
    status: str | None = Field(None, max_length=20)
    page: int = Field(1, ge=1, le=100000)
    page_size: int = Field(25, ge=1, le=100)
    alerts_only: bool = False

    @field_validator("days", mode="before")
    @classmethod
    def parse_days_query(cls, value):
        # HTTP query values are strings; integer Literals do not coerce them.
        if isinstance(value, str) and value in {"1", "7", "30"}:
            return int(value)
        return value


class Metrics(BaseModel):
    calls: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    priced_calls: int
    missing_usage_calls: int
    error_calls: int
    failover_calls: int


class Summary(Metrics):
    median_ms: float | None
    p95_ms: float | None


class Daily(Metrics):
    day: date


class Breakdown(Metrics):
    module_name: str
    model_name: str


class Usage(BaseModel):
    id: int
    operation_id: str
    module_name: str
    model_name: str
    status: str
    input_tokens: int | None
    output_tokens: int | None
    cached_tokens: int | None
    reasoning_tokens: int | None
    latency_ms: float
    estimated_cost_usd: float | None
    pricing_version: str
    attempt: int
    created_at: datetime


class Logs(BaseModel):
    items: list[Usage]
    total: int
    page: int
    page_size: int
    has_next: bool


class Options(BaseModel):
    modules: list[str]
    models: list[str]
    statuses: list[str]


class Alerts(BaseModel):
    count: int
    latency_ms: float
    tokens: float


class OpsDashboard(BaseModel):
    start: datetime
    end: datetime
    summary: Summary
    daily: list[Daily]
    breakdown: list[Breakdown]
    options: Options
    dlq_count: int
    alerts: Alerts
    logs: Logs
