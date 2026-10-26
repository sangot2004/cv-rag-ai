import json
import sys
import types

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from src.ops.optimization import (
    DEFAULTS,
    OptimizationConfig,
    OptimizationPointer,
    active_config,
    rollback,
    validate_config,
    cached_extract,
)
from src.ops.experiments import score


@pytest.fixture
def config_store(monkeypatch):
    engine = create_engine("sqlite://")
    OptimizationConfig.__table__.create(engine)
    OptimizationPointer.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setitem(sys.modules, "src.db.session", types.SimpleNamespace(SessionLocal=factory))
    yield factory
    engine.dispose()


def test_active_config_defaults_only_without_selected_config(config_store):
    assert active_config() == DEFAULTS
    with config_store() as session:
        session.add(OptimizationPointer(id=1))
        session.commit()
    assert active_config() == DEFAULTS


def test_active_config_rejects_missing_selected_config(config_store):
    with config_store() as session:
        session.add(OptimizationPointer(id=1, config_id="missing"))
        session.commit()

    with pytest.raises(LookupError, match="Active optimization config 'missing' is missing"):
        active_config()


@pytest.mark.parametrize("settings_json", ["{bad-json", '{"extraction_prompt_version":"latest"}'])
def test_active_config_rejects_invalid_selected_config(config_store, settings_json):
    with config_store() as session:
        session.add(OptimizationPointer(id=1, config_id="broken"))
        session.add(OptimizationConfig(id="broken", settings_json=settings_json, status="approved"))
        session.commit()

    with pytest.raises(ValueError, match="Active optimization config 'broken' is invalid"):
        active_config()


def test_active_config_surfaces_database_error(monkeypatch):
    engine = create_engine("sqlite://")
    factory = sessionmaker(bind=engine)
    monkeypatch.setitem(sys.modules, "src.db.session", types.SimpleNamespace(SessionLocal=factory))

    with pytest.raises(RuntimeError, match="Could not read active optimization config") as error:
        active_config()
    assert isinstance(error.value.__cause__, SQLAlchemyError)
    engine.dispose()


def test_config_limits():
    for value in (0, 1, 9, True):
        with pytest.raises(ValueError):
            validate_config({"retrieval_multiplier": value})


def test_unknown_config():
    with pytest.raises(ValueError):
        validate_config({"prompt": "arbitrary"})


def test_defaults():
    assert validate_config({})["cache_enabled"] is False
    assert validate_config({})["extraction_prompt_version"] == "55c22bda"


def test_prompt_version_requires_immutable_commit():
    for version in (None, "", "latest", "production", "1234567", "g" * 8):
        with pytest.raises(ValueError, match="pinned LangSmith commit"):
            validate_config({"extraction_prompt_version": version})


def test_quality_missing_fields():
    assert score({"name": "A"}, {"name": "A", "skill": "Python"}) == .5


def test_disabled_cache():
    assert cached_extract("text", "model", "prompt", None, lambda: 42, False) == 42


def test_approval_rejects_stale_baseline_and_rollback(monkeypatch):
    import sys
    import types
    import json

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.db.models import Base
    from src.ops.optimization import OptimizationConfig, OptimizationPointer, approve, rollback, active_config

    engine = create_engine('sqlite://')
    OptimizationConfig.__table__.create(engine)
    OptimizationPointer.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setitem(sys.modules, 'src.db.session', types.SimpleNamespace(SessionLocal=factory))
    from src.ingestion import locking
    monkeypatch.setattr(locking.database, 'SessionLocal', factory)
    default_config = validate_config({})
    good_config = validate_config({'cache_enabled': True})
    with factory() as session:
        session.add(OptimizationPointer(id=1))
        session.add(OptimizationConfig(id='good', settings_json=json.dumps(good_config),
                    report_json=json.dumps({'passed': True, 'baseline_config_id': None,
                                            'baseline_config': default_config, 'proposed_config': good_config}),
                    status='proposed'))
        session.add(OptimizationConfig(id='stale', settings_json=json.dumps(default_config),
                    report_json=json.dumps({'passed': True, 'baseline_config_id': None,
                                            'baseline_config': default_config, 'proposed_config': default_config}),
                    status='proposed'))
        session.add(OptimizationConfig(id='changed-prompt', settings_json=json.dumps(validate_config(
                    {'extraction_prompt_version': 'deadbeef'})),
                    report_json=json.dumps({'passed': True, 'baseline_config_id': None,
                                            'baseline_config': default_config, 'proposed_config': default_config}),
                    status='proposed'))
        session.commit()

    from src.auth import service as auth
    monkeypatch.setattr(auth, "require_admin", lambda: auth.Identity("test-admin", "admin", "admin", None))
    with pytest.raises(ValueError):
        approve('changed-prompt')
    approve('good')
    assert active_config()['cache_enabled']
    with pytest.raises(ValueError):
        approve('stale')

    rollback()
    assert not active_config()['cache_enabled']


def test_cache_keys_change_with_prompt(monkeypatch):
    import redis
    from pydantic import BaseModel

    class Schema(BaseModel):
        name: str
    store = {}

    class FakeRedis:
        def get(self, key): return store.get(key)
        def setex(self, key, ttl, value): store[key] = value
    monkeypatch.setattr(redis.Redis, 'from_url', lambda *a, **k: FakeRedis())
    calls = []

    def compute():
        calls.append(1)
        return Schema(name='A')
    for prompt in ['v1', 'v1', 'v2']:
        assert cached_extract('CV', 'm', prompt, Schema, compute, True).name == 'A'
    assert len(calls) == 2
