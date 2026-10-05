import pytest
from src.ops.optimization import active_config, rollback, validate_config, cached_extract
from src.ops.experiments import score


def test_config_limits():
    for value in (0, 1, 9, True):
        with pytest.raises(ValueError):
            validate_config({"retrieval_multiplier": value})


def test_unknown_config():
    with pytest.raises(ValueError):
        validate_config({"prompt": "arbitrary"})


def test_defaults():
    assert validate_config({})["cache_enabled"] is False


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
    with factory() as session:
        session.add(OptimizationPointer(id=1))
        session.add(OptimizationConfig(id='good', settings_json=json.dumps(validate_config(
            {'cache_enabled': True})), report_json=json.dumps({'passed': True, 'baseline_config_id': None}), status='proposed'))
        session.add(OptimizationConfig(id='stale', settings_json=json.dumps(validate_config({})),
                    report_json=json.dumps({'passed': True, 'baseline_config_id': None}), status='proposed'))
        session.commit()

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
