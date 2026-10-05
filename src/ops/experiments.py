import json
import time

from sqlalchemy import select
from src.ops.optimization import OptimizationConfig, OptimizationPointer


def flatten(value, prefix=""):
    if isinstance(value, dict):
        return {k: v for key, child in value.items() for k, v in flatten(child, prefix + "/" + str(key)).items()}

    if isinstance(value, list):
        return {k: v for i, child in enumerate(value) for k, v in flatten(child, prefix + "/" + str(i)).items()}

    return {prefix: value}


def normalize(value):
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    return value


def score(actual, expected):
    truth = flatten(expected)
    predicted = flatten(actual)

    truth = {
        key: value
        for key, value in truth.items()
        if key != "/skills" and not key.startswith("/skills/")
    }

    matched = sum(
        key in predicted
        and normalize(predicted[key]) == normalize(value)
        for key, value in truth.items()
    )
    total = len(truth)

    if "skills" in expected:
        expected_skills = {
            normalize(skill)
            for skill in expected["skills"]
        }
        actual_skills = {
            normalize(skill)
            for skill in actual.get("skills", [])
        }

        union = expected_skills | actual_skills
        skills_score = (
            len(expected_skills & actual_skills) / len(union)
            if union else 1.0
        )

        if "skills" not in actual:
            skills_score = 0.0

        matched += skills_score
        total += 1

    return matched / total if total else 0.0


def run_experiment(identifier, dataset_name):
    from langsmith import Client

    from src.db.session import SessionLocal
    from src.ops.optimization import validate_config, DEFAULTS
    from src.config.settings import get_settings
    from src.schemas.cv_schema import CVSchema
    from src.ingestion.extraction.llm_extractor import _extract_call
    from src.llm.key_manager import call_with_key_failover
    from src.ops.telemetry import operation_scope
    from src.db.models import LLMUsageLog

    client = Client()
    examples = list(client.list_examples(dataset_name=dataset_name))
    if not examples:
        raise ValueError("Golden dataset is empty")

    for example in examples:
        CVSchema.model_validate(example.outputs)
        if not isinstance(example.inputs.get("raw_text"), str) or not example.inputs["raw_text"].strip():
            raise ValueError("Each input must contain raw_text")

    with SessionLocal() as session:
        row = session.get(OptimizationConfig, identifier)
        if not row or row.status == "approved":
            raise ValueError("Unknown or already approved proposal")

        proposed = validate_config(json.loads(row.settings_json))
        pointer = session.get(OptimizationPointer, 1)
        baseline_id = pointer.config_id
        baseline_row = session.get(OptimizationConfig, baseline_id) if baseline_id else None
        baseline = validate_config(json.loads(baseline_row.settings_json)) if baseline_row else DEFAULTS

    if proposed["retrieval_multiplier"] != baseline["retrieval_multiplier"]:
        raise ValueError("Retrieval changes require a labeled retrieval experiment; unsupported by this runner")

    from langsmith import traceable

    @traceable(name="ops_extraction_evaluation")
    def evaluated_call(raw_text, model):
        return call_with_key_failover(lambda key: _extract_call(key, raw_text, model))

    results = {}
    for label, config in [("baseline", baseline), ("proposal", proposed)]:
        project = client.create_project(
            project_name=f"ops-{identifier}-{label}-{time.time_ns()}", reference_dataset_id=examples[0].dataset_id)
        measurements = []
        for example in examples:
            with operation_scope("optimization_experiment") as context:
                started = time.perf_counter()
                quality = 0.0
                ok = False
                try:
                    from langsmith import tracing_context
                    with tracing_context(project_name=project.name, enabled=True):
                        value = evaluated_call(example.inputs["raw_text"], config["extraction_model"] or get_settings().GEMINI_LLM_MODEL, langsmith_extra={
                                               "reference_example_id": example.id, "metadata": {"proposal_id": identifier, "variant": label}})
                    quality = score(value.model_dump(mode="json"), CVSchema.model_validate(
                        example.outputs).model_dump(mode="json"))
                    ok = True
                except Exception:
                    pass

                elapsed = (time.perf_counter()-started)*1000
                with SessionLocal() as session:
                    logs = session.execute(select(LLMUsageLog).where(
                        LLMUsageLog.operation_id == context["operation_id"])).scalars().all()
                    cost = sum(x.estimated_cost_usd for x in logs) if logs and all(
                        x.estimated_cost_usd is not None for x in logs) else None
                    tokens = sum((x.input_tokens or 0)+(x.output_tokens or 0) for x in logs) if logs and all(
                        x.input_tokens is not None and x.output_tokens is not None for x in logs) else None

                measurements.append({"example_id": str(example.id), "quality": quality,
                                    "success": ok, "latency_ms": elapsed, "cost": cost, "tokens": tokens})

        results[label] = {"project": project.name, "samples": measurements, "quality": sum(
            x["quality"] for x in measurements)/len(measurements), "success": all(x["success"] for x in measurements)}

    min_quality = 0.85

    passed = (
        results["proposal"]["success"]
        and results["baseline"]["success"]
        and results["proposal"]["quality"]
        >= results["baseline"]["quality"]
        and results["proposal"]["quality"] >= min_quality
    )

    def totals(label, field):
        values = [x[field] for x in results[label]["samples"]]
        return sum(values) if all(x is not None for x in values) else None

    base_cost, next_cost = totals("baseline", "cost"), totals("proposal", "cost")
    base_tokens, next_tokens = totals("baseline", "tokens"), totals("proposal", "tokens")
    base_latency = sum(x["latency_ms"] for x in results["baseline"]["samples"])
    next_latency = sum(x["latency_ms"] for x in results["proposal"]["samples"])
    improved = ((base_cost is not None and next_cost is not None and next_cost < base_cost)
                or (base_tokens is not None and next_tokens is not None and next_tokens < base_tokens)
                or next_latency < base_latency
                or (proposed == {**baseline, "cache_enabled": True} and not baseline["cache_enabled"]))

    passed = passed and improved
    report = {"improved": improved, "experiment_cost_usd": base_cost + next_cost if base_cost is not None and next_cost is not None else None, "baseline_config_id": baseline_id,
              "dataset": dataset_name, "passed": passed, "results": results, "metric": "exact leaf match (list order sensitive); not semantic quality", "evaluated_at": time.time()}

    with SessionLocal() as session:
        row = session.get(OptimizationConfig, identifier)
        if row.status == "approved":
            raise ValueError("Proposal activated while experiment was running")
        row.report_json = json.dumps(report)
        session.commit()
    return report
