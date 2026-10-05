import logging
import json
import os
import time
import uuid

from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
from datetime import datetime, timezone
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)
_context = ContextVar("ops_context", default={})


@contextmanager
def operation_scope(module_name, **refs):
    parent = _context.get()
    context = {**parent, **{k: v for k, v in refs.items() if v is not None}, "module_name": module_name}
    if not parent.get("operation_id"):
        context["operation_id"] = str(uuid.uuid4())
    token = _context.set(context)
    try:
        yield context
    finally:
        _context.reset(token)


def monitored(module_name, ref=None):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            refs = {}
            if ref:
                import inspect
                values = inspect.signature(fn).bind_partial(*args, **kwargs).arguments
                if ref in values:
                    refs[ref] = values[ref]
            with operation_scope(module_name, **refs):
                return fn(*args, **kwargs)
        return wrapped
    return decorate


def estimate_cost(model, input_tokens, output_tokens, cached_tokens=0):
    try:
        prices = json.loads(os.getenv("OPS_MODEL_PRICES_JSON", "{}"))
        rate = prices.get(model)
        if rate is None or input_tokens is None or output_tokens is None:
            return None
        cached = min(cached_tokens or 0, input_tokens)
        return ((input_tokens-cached) * float(rate["input"]) + cached * float(rate.get("cached_input", rate["input"])) + output_tokens * float(rate["output"])) / 1_000_000
    except (ValueError, KeyError, TypeError):
        logger.warning("Invalid OPS_MODEL_PRICES_JSON")
        return None


def record_usage(model, latency_ms, usage=None, status="success", error_type=None, run_id=None, context=None):
    if os.getenv("OPS_ENABLED", "true").lower() != "true":
        return
    usage = usage or {}
    context = context or _context.get()
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    details = usage.get("input_token_details") or {}
    cached = details.get("cache_read", 0)
    cost = estimate_cost(model, input_tokens, output_tokens, cached)
    try:
        from src.db.models import LLMUsageLog
        from src.db.session import SessionLocal

        with SessionLocal() as session:
            session.add(LLMUsageLog(
                operation_id=context.get("operation_id", str(uuid.uuid4())),
                module_name=context.get("module_name", "unknown"),
                job_id=context.get("job_id"), candidate_id=context.get("candidate_id"),
                thread_id=context.get("thread_id"), model_name=model,
                input_tokens=input_tokens, output_tokens=output_tokens,
                cached_tokens=cached, reasoning_tokens=(usage.get("output_token_details") or {}).get("reasoning"),
                latency_ms=latency_ms, estimated_cost_usd=cost,
                pricing_version=os.getenv("OPS_PRICING_VERSION", "unconfigured"),
                status=status, attempt=context.get("attempt", 1), error_type=error_type, langsmith_run_id=str(run_id) if run_id else None,
                created_at=datetime.now(timezone.utc),
            ))
            session.commit()
    except Exception:
        logger.exception("Could not persist AI usage")


class UsageCallback(BaseCallbackHandler):
    def __init__(self, model):
        self.model = model
        self.runs = {}

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        self.runs[run_id] = (time.perf_counter(), dict(_context.get()))

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs):
        self.runs[run_id] = (time.perf_counter(), dict(_context.get()))

    def on_llm_end(self, response, *, run_id, **kwargs):
        started, context = self.runs.pop(run_id, (time.perf_counter(), dict(_context.get())))
        usage = None
        if response.generations and response.generations[0]:
            msg = getattr(response.generations[0][0], "message", None)
            usage = getattr(msg, "usage_metadata", None)
        record_usage(self.model, (time.perf_counter() - started)*1000, usage, run_id=run_id, context=context)

    def on_llm_error(self, error, *, run_id, **kwargs):
        started, context = self.runs.pop(run_id, (time.perf_counter(), dict(_context.get())))
        record_usage(self.model, (time.perf_counter() - started)*1000, status="error",
                     error_type=type(error).__name__, run_id=run_id, context=context)
