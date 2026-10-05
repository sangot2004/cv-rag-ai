import time
from unittest.mock import patch, MagicMock
from src.ops.telemetry import operation_scope, _context, estimate_cost, record_usage, UsageCallback


def test_scope_groups_child_calls_and_restores():
    with operation_scope("ingestion", job_id="j1") as outer:
        with operation_scope("extraction") as child:
            assert child["operation_id"] == outer["operation_id"]
            assert child["job_id"] == "j1"
        assert _context.get()["module_name"] == "ingestion"
    assert _context.get() == {}


def test_unknown_pricing_is_not_zero(monkeypatch):
    monkeypatch.setenv("OPS_MODEL_PRICES_JSON", "{}")
    assert estimate_cost("unknown", 10, 20) is None


def test_price_separates_cached_input(monkeypatch):
    monkeypatch.setenv("OPS_MODEL_PRICES_JSON", '{"m":{"input": 2, "output": 4, "cached_input": 1}}')
    assert estimate_cost("m", 1_000_000, 1_000_000, 500_000) == 5.5
    assert estimate_cost("m", None, 0) is None


def test_callback_records_success_and_error():
    cb = UsageCallback("m")
    response = MagicMock()
    response.generations[0][0].message.usage_metadata = {"input_tokens": 12, "output_tokens": 3}
    with patch("src.ops.telemetry.record_usage") as log:
        cb.on_chat_model_start({}, [], run_id="a")
        cb.on_llm_end(response, run_id="a")
        assert log.call_args.args[2]["input_tokens"] == 12
        cb.on_chat_model_start({}, [], run_id="b")
        cb.on_llm_error(ValueError("error"), run_id="b")
        assert log.call_args.kwargs["status"] == "error"
        assert not cb.runs


def test_record_failure_does_not_break_business():
    with patch("src.db.session.SessionLocal", side_effect=RuntimeError("DB unavailable")):
        record_usage("m", 1, {"input_tokens": 1, "output_tokens": 2})


def test_usage_persistence_and_migration_sqlite(monkeypatch):
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, select, inspect
    from sqlalchemy.orm import sessionmaker
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from src.db.models import LLMUsageLog
    engine = create_engine('sqlite://')
    spec = importlib.util.spec_from_file_location(
        'usage_migration', Path('alembic/versions/add_llm_usage_logs.py'))
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
    factory = sessionmaker(bind=engine)
    monkeypatch.setenv('OPS_ENABLED', 'true')
    monkeypatch.setenv('OPS_MODEL_PRICES_JSON', '{"m":{"input":1,"output":2}}')
    with patch('src.db.session.SessionLocal', factory), operation_scope('extraction', job_id='j1'):
        record_usage('m', 20, {'input_tokens': 100, 'output_tokens': 50})
    with factory() as session:
        row = session.execute(select(LLMUsageLog)).scalar_one()
        assert row.job_id == 'j1'
        assert row.input_tokens == 100
        assert abs(row.estimated_cost_usd - .0002) < 1e-9
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()
    assert 'llm_usage_logs' not in inspect(engine).get_table_names()
