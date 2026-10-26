"""Read-only Ops queries. Aggregate in SQL; never return prompts or provider payloads."""
import math
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, or_, select

from src.auth.service import admin_only
from src.db import session as database
from src.db.models import IngestionJob, LLMUsageLog as Log


def _threshold(name, default):
    try:
        value = float(os.getenv(name, str(default)))
        return value if math.isfinite(value) and value >= 0 else default
    except ValueError:
        return default


def _metrics():
    return [func.count(Log.id).label("calls"),
            func.coalesce(func.sum(Log.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(Log.output_tokens), 0).label("output_tokens"),
            func.sum(Log.estimated_cost_usd).label("estimated_cost_usd"),
            func.count(Log.estimated_cost_usd).label("priced_calls"),
            func.count(case((or_(Log.input_tokens.is_(None), Log.output_tokens.is_(None)), 1))).label("missing_usage_calls"),
            func.count(case((Log.status == "error", 1))).label("error_calls"),
            func.count(case((Log.attempt > 1, 1))).label("failover_calls")]


def _percentile(db, conditions, count, fraction):
    if not count:
        return None
    position = (count - 1) * fraction
    low = math.floor(position)
    values = db.scalars(select(Log.latency_ms).where(*conditions)
                        .order_by(Log.latency_ms, Log.id).offset(low).limit(2)).all()
    return float(values[0] + (values[-1] - values[0]) * (position - low))


@admin_only
def dashboard(days=7, module=None, model=None, status=None, page=1, page_size=25, alerts_only=False):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    window = [Log.created_at >= start.replace(tzinfo=None), Log.created_at < end.replace(tzinfo=None)]
    conditions = list(window)
    for column, value in ((Log.module_name, module), (Log.model_name, model), (Log.status, status)):
        if value:
            conditions.append(column == value)
    latency_limit = _threshold("OPS_LATENCY_ALERT_MS", 15000)
    token_limit = _threshold("OPS_TOKEN_ALERT", 20000)
    alert = or_(Log.status == "error", Log.latency_ms > latency_limit,
                func.coalesce(Log.input_tokens, 0) + func.coalesce(Log.output_tokens, 0) > token_limit)
    with database.SessionLocal() as db:
        summary = dict(db.execute(select(*_metrics()).where(*conditions)).mappings().one())
        summary["median_ms"] = _percentile(db, conditions, summary["calls"], .5)
        summary["p95_ms"] = _percentile(db, conditions, summary["calls"], .95)
        dlq = db.scalar(select(func.count()).select_from(IngestionJob).where(IngestionJob.status == "dlq"))
        alert_count = db.scalar(select(func.count(Log.id)).where(*conditions, alert))
        day = func.date(Log.created_at)
        daily = [dict(row) for row in db.execute(select(day.label("day"), *_metrics())
                 .where(*conditions).group_by(day).order_by(day)).mappings()]
        breakdown = [dict(row) for row in db.execute(select(Log.module_name, Log.model_name, *_metrics())
                     .where(*conditions).group_by(Log.module_name, Log.model_name)
                     .order_by(Log.module_name, Log.model_name)).mappings()]
        options = {key: list(db.scalars(select(column).where(*window).distinct().order_by(column)))
                   for key, column in (("modules", Log.module_name), ("models", Log.model_name), ("statuses", Log.status))}
        log_conditions = conditions + ([alert] if alerts_only else [])
        total = alert_count if alerts_only else summary["calls"]
        # Explicit allowlist. Raw error text, CV, prompt and API keys are never part of this DTO.
        columns = [Log.id, Log.operation_id, Log.module_name, Log.model_name, Log.status,
                   Log.input_tokens, Log.output_tokens, Log.cached_tokens, Log.reasoning_tokens,
                   Log.latency_ms, Log.estimated_cost_usd, Log.pricing_version, Log.attempt, Log.created_at]
        items = [dict(row) for row in db.execute(select(*columns).where(*log_conditions)
                 .order_by(Log.created_at.desc(), Log.id.desc()).offset((page - 1) * page_size)
                 .limit(page_size)).mappings()]
        for row in items:
            row["created_at"] = row["created_at"].replace(tzinfo=timezone.utc)
    return {"start": start, "end": end, "summary": summary, "daily": daily,
            "breakdown": breakdown, "options": options, "dlq_count": dlq,
            "alerts": {"count": alert_count, "latency_ms": latency_limit, "tokens": token_limit},
            "logs": {"items": items, "total": total, "page": page, "page_size": page_size,
                     "has_next": page * page_size < total}}
