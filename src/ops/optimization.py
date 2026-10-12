import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Integer, select
from sqlalchemy.exc import SQLAlchemyError

from src.db.models import Base
from src.auth.service import admin_only
from src.llm.prompt_store import format_prompt


class OptimizationConfig(Base):
    __tablename__ = "ops_optimization_configs"

    id = Column(String(36), primary_key=True)
    settings_json = Column(Text, nullable=False)
    report_json = Column(Text)
    status = Column(String(24), nullable=False, default="proposed")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class OptimizationPointer(Base):
    __tablename__ = "ops_optimization_pointer"

    id = Column(Integer, primary_key=True)
    config_id = Column(String(36))


LEGACY_EXTRACTION_PROMPT_COMMIT = "55c22bda"
DEFAULTS = {
    "extraction_model": None,
    "extraction_prompt_version": LEGACY_EXTRACTION_PROMPT_COMMIT,
    "cache_enabled": False,
    "retrieval_multiplier": 2,
}


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("Configuration must be an object")
    if set(config) - set(DEFAULTS):
        raise ValueError("Unsupported configuration keys")

    value = {**DEFAULTS, **config}
    if type(value["cache_enabled"]) is not bool:
        raise ValueError("cache_enabled must be boolean")

    if type(value["retrieval_multiplier"]) is not int or not 2 <= value["retrieval_multiplier"] <= 8:
        raise ValueError("retrieval_multiplier must be 2..8")

    if value["extraction_model"] is not None and (not isinstance(value["extraction_model"], str) or not value["extraction_model"].strip()):
        raise ValueError("Invalid model")

    version = value["extraction_prompt_version"]
    if not isinstance(version, str) or not re.fullmatch(r"[0-9a-f]{8,40}", version):
        raise ValueError("Extraction prompt version must be a pinned LangSmith commit")

    return value


def active_config():
    from src.db.session import SessionLocal

    try:
        with SessionLocal() as session:
            pointer = session.get(OptimizationPointer, 1)
            if pointer is None or pointer.config_id is None:
                return dict(DEFAULTS)
            config_id = pointer.config_id
            row = session.get(OptimizationConfig, config_id)
            if row is None:
                raise LookupError(f"Active optimization config {config_id!r} is missing")
            settings_json = row.settings_json
    except SQLAlchemyError as exc:
        raise RuntimeError("Could not read active optimization config from the database") from exc

    try:
        return validate_config(json.loads(settings_json))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Active optimization config {config_id!r} is invalid: {exc}") from exc


@admin_only
def propose(config):
    from src.db.session import SessionLocal

    config = validate_config(config)
    with SessionLocal() as session:
        identifier = str(uuid.uuid4())
        session.add(OptimizationConfig(id=identifier, settings_json=json.dumps(config), status="proposed"))
        session.commit()
        return identifier


@admin_only
def approve(identifier):
    from src.db.session import SessionLocal

    with SessionLocal() as session:

        pointer = session.execute(select(OptimizationPointer).where(
            OptimizationPointer.id == 1).with_for_update()).scalar_one()
        row = session.get(OptimizationConfig, identifier)

        if not row or not row.report_json:
            raise ValueError("Run an experiment first")

        report = json.loads(row.report_json)
        baseline_row = session.get(OptimizationConfig, pointer.config_id) if pointer.config_id else None
        baseline = validate_config(json.loads(baseline_row.settings_json)) if baseline_row else dict(DEFAULTS)
        proposed = validate_config(json.loads(row.settings_json))
        if (not report.get("passed")
                or report.get("baseline_config_id") != pointer.config_id
                or report.get("baseline_config") != baseline
                or report.get("proposed_config") != proposed):
            raise ValueError("Experiment failed or baseline changed; rerun experiment")

        row.status = "approved"
        pointer.config_id = identifier
        session.commit()


@admin_only
def rollback(identifier=None):
    from src.db.session import SessionLocal

    with SessionLocal() as session:
        pointer = session.execute(select(OptimizationPointer).where(
            OptimizationPointer.id == 1).with_for_update()).scalar_one()
        row = session.get(OptimizationConfig, identifier) if identifier else None

        if identifier and (not row or row.status != "approved"):
            raise ValueError("Rollback target must have been approved")

        pointer.config_id = identifier
        session.commit()


def cached_extract(text, model, prompt, schema, compute, enabled):
    if not enabled:
        return compute()

    key = "ops:extract:" + \
        hashlib.sha256(json.dumps([text, model, prompt, schema.model_json_schema()],
                       sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    client = None
    try:
        import redis
        from src.config.settings import get_settings
        client = redis.Redis.from_url(get_settings().REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        hit = client.get(key)
        if hit:
            return schema.model_validate_json(hit)
    except Exception:
        pass

    result = compute()
    if client:
        try:
            client.setex(key, int(os.getenv("OPS_CACHE_TTL_SECONDS", "86400")), result.model_dump_json())
        except Exception:
            pass

    return result


@admin_only
def analyze_usage():
    from sqlalchemy import func
    from src.db.models import LLMUsageLog
    from src.db.session import SessionLocal
    from src.config.settings import get_settings
    from src.llm.key_manager import call_with_key_failover
    from src.ops.telemetry import UsageCallback, operation_scope
    from langchain_google_genai import ChatGoogleGenerativeAI
    from pydantic import BaseModel

    class Suggestion(BaseModel):
        rationale: str
        cache_enabled: bool
        extraction_model: str | None = None

    with SessionLocal() as s:
        rows = s.execute(select(LLMUsageLog.module_name, LLMUsageLog.model_name, func.count(), func.avg(LLMUsageLog.latency_ms), func.sum(
            LLMUsageLog.input_tokens), func.sum(LLMUsageLog.estimated_cost_usd)).group_by(LLMUsageLog.module_name, LLMUsageLog.model_name)).all()

    if not rows:
        raise ValueError("No usage data to analyze")

    allowed_models = [x.strip() for x in os.getenv("OPS_ROUTING_MODELS",
                                                   get_settings().GEMINI_LLM_MODEL).split(",") if x.strip()]
    prompt = format_prompt(
        "cv-rag-optimization-analysis",
        allowed_models=json.dumps(allowed_models),
        usage_data=json.dumps([list(row) for row in rows], default=str),
    )
    model = get_settings().GEMINI_LLM_MODEL

    with operation_scope("optimization_analysis"):
        result = call_with_key_failover(lambda key: ChatGoogleGenerativeAI(model=model, google_api_key=key, callbacks=[
                                        UsageCallback(model)]).with_structured_output(Suggestion).invoke(prompt))

    if result.extraction_model and result.extraction_model not in allowed_models:
        raise ValueError("Suggested model is not allowlisted")

    config = active_config()
    config.update(cache_enabled=result.cache_enabled, extraction_model=result.extraction_model)

    return {"proposal_id": propose(config), "rationale": result.rationale}
