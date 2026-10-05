import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Integer, select

from src.db.models import Base


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


DEFAULTS = {"extraction_model": None, "cache_enabled": False, "retrieval_multiplier": 2}


def validate_config(config):
    if set(config) - set(DEFAULTS):
        raise ValueError("Unsupported configuration keys")

    value = {**DEFAULTS, **config}
    if type(value["cache_enabled"]) is not bool:
        raise ValueError("cache_enabled must be boolean")

    if type(value["retrieval_multiplier"]) is not int or not 2 <= value["retrieval_multiplier"] <= 8:
        raise ValueError("retrieval_multiplier must be 2..8")

    if value["extraction_model"] is not None and (not isinstance(value["extraction_model"], str) or not value["extraction_model"].strip()):
        raise ValueError("Invalid model")

    return value


def active_config():
    from src.db.session import SessionLocal

    try:
        with SessionLocal() as session:
            pointer = session.get(OptimizationPointer, 1)
            row = session.get(OptimizationConfig, pointer.config_id) if pointer and pointer.config_id else None
            return validate_config(json.loads(row.settings_json)) if row else dict(DEFAULTS)

    except Exception:
        return dict(DEFAULTS)


def propose(config):
    from src.db.session import SessionLocal

    config = validate_config(config)
    with SessionLocal() as session:
        identifier = str(uuid.uuid4())
        session.add(OptimizationConfig(id=identifier, settings_json=json.dumps(config), status="proposed"))
        session.commit()
        return identifier


def approve(identifier):
    from src.db.session import SessionLocal

    with SessionLocal() as session:

        pointer = session.execute(select(OptimizationPointer).where(
            OptimizationPointer.id == 1).with_for_update()).scalar_one()
        row = session.get(OptimizationConfig, identifier)

        if not row or not row.report_json:
            raise ValueError("Run an experiment first")

        report = json.loads(row.report_json)
        if not report.get("passed") or report.get("baseline_config_id") != pointer.config_id:
            raise ValueError("Experiment failed or baseline changed; rerun experiment")

        row.status = "approved"
        pointer.config_id = identifier
        session.commit()


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
    prompt = "Suggest extraction optimization from aggregate usage. No activation. Models allowed: " + \
        json.dumps(allowed_models) + ". Do not claim measured savings or quality. Enable exact cache only if useful. Data: " + \
        json.dumps([list(row) for row in rows], default=str)
    model = get_settings().GEMINI_LLM_MODEL

    with operation_scope("optimization_analysis"):
        result = call_with_key_failover(lambda key: ChatGoogleGenerativeAI(model=model, google_api_key=key, callbacks=[
                                        UsageCallback(model)]).with_structured_output(Suggestion).invoke(prompt))

    if result.extraction_model and result.extraction_model not in allowed_models:
        raise ValueError("Suggested model is not allowlisted")

    config = active_config()
    config.update(cache_enabled=result.cache_enabled, extraction_model=result.extraction_model)

    return {"proposal_id": propose(config), "rationale": result.rationale}
