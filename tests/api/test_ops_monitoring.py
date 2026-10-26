from datetime import datetime, timedelta, timezone
import pytest
from src.db.models import LLMUsageLog, IngestionJob


def seed(api):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with api.db() as db:
        for i, cost in enumerate([0.0, None, .02, None]):
            db.add(LLMUsageLog(operation_id=f"op-{i}", module_name="extract" if i < 3 else "chat",
                model_name="free" if i < 2 else "paid", input_tokens=100 if i != 1 else None,
                output_tokens=20 if i != 1 else None, cached_tokens=10,
                latency_ms=[100, 200, 300, 20000][i], estimated_cost_usd=cost,
                attempt=2 if i == 3 else 1, pricing_version="test", status="error" if i == 1 else "success",
                error_type="SECRET provider payload", thread_id="private-thread", created_at=now - timedelta(minutes=i)))
        db.add(LLMUsageLog(operation_id="old", module_name="old", model_name="old", latency_ms=999,
            pricing_version="test", status="success", created_at=now-timedelta(days=40)))
        db.commit()


def get(api, query="", user="admin"):
    return api.client.get("/api/ops/dashboard" + query, headers=api.headers(user))


def test_ops_auth_validation(api):
    assert api.client.get("/api/ops/dashboard").status_code == 401
    assert get(api, user="alice").status_code == 403
    for query in ("?days=365", "?page=0", "?page_size=101", "?unknown=1", "?alerts_only=bad"):
        assert get(api, query).status_code == 422


def test_ops_summary_cost_percentiles_and_redaction(api):
    seed(api)
    response = get(api)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "private, no-store"
    body = response.json()
    summary = body["summary"]
    assert summary["calls"] == 4
    assert summary["input_tokens"] == 300
    assert summary["output_tokens"] == 60
    assert summary["missing_usage_calls"] == 1
    assert summary["priced_calls"] == 2
    assert summary["estimated_cost_usd"] == pytest.approx(.02)
    assert summary["median_ms"] == 250
    assert summary["p95_ms"] == pytest.approx(17045)
    assert summary["error_calls"] == summary["failover_calls"] == 1
    assert body["alerts"]["count"] == 2
    assert sum(row["calls"] for row in body["daily"]) == 4
    assert sum(row["calls"] for row in body["breakdown"]) == 4
    assert body["options"]["modules"] == ["chat", "extract"]
    assert "SECRET" not in response.text and "private-thread" not in response.text
    assert body["logs"]["items"][0]["created_at"].endswith("Z")


def test_ops_zero_unknown_filters_and_pagination(api):
    seed(api)
    free = get(api, "?module=extract&model=free&status=success").json()
    assert free["summary"]["estimated_cost_usd"] == 0
    assert free["summary"]["priced_calls"] == free["summary"]["calls"] == 1
    unknown = get(api, "?status=error").json()
    assert unknown["summary"]["estimated_cost_usd"] is None
    assert unknown["breakdown"][0]["estimated_cost_usd"] is None
    assert unknown["daily"][0]["estimated_cost_usd"] is None
    first = get(api, "?page_size=2").json()["logs"]
    second = get(api, "?page_size=2&page=2").json()["logs"]
    assert first["has_next"] and not second["has_next"]
    assert not ({r["id"] for r in first["items"]} & {r["id"] for r in second["items"]})
    alerts = get(api, "?alerts_only=true").json()
    assert alerts["logs"]["total"] == 2 and alerts["summary"]["calls"] == 4


def test_ops_empty_still_returns_dlq(api, monkeypatch):
    with api.db() as db:
        db.add(IngestionJob(job_id="dlq-job", source_type="web_upload", source_reference="private",
            original_filename="private.pdf", minio_bucket="test", minio_object_key="test.pdf", file_type="pdf", status="dlq"))
        db.commit()
    monkeypatch.setenv("OPS_LATENCY_ALERT_MS", "nan")
    monkeypatch.setenv("OPS_TOKEN_ALERT", "invalid")
    body = get(api).json()
    assert body["dlq_count"] == 1
    assert body["summary"]["calls"] == 0
    assert body["summary"]["estimated_cost_usd"] is None
    assert body["summary"]["p95_ms"] is None
    assert body["alerts"]["latency_ms"] == 15000
    assert body["alerts"]["tokens"] == 20000
    assert body["logs"]["items"] == []


@pytest.mark.parametrize("days", [1, 7, 30])
def test_ops_days_query_parameter(api, days):
    seed(api)
    response = get(api, f"?days={days}")
    assert response.status_code == 200, response.text
    body = response.json()
    start = datetime.fromisoformat(body["start"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(body["end"].replace("Z", "+00:00"))
    assert end - start == timedelta(days=days)
    assert body["summary"]["calls"] == 4


@pytest.mark.parametrize("days", ["0", "2", "31", "abc", "7.5", ""])
def test_ops_invalid_days_query_parameter(api, days):
    assert get(api, f"?days={days}").status_code == 422
