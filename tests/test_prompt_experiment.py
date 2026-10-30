import json
import sys
import types
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth import service as auth
from src.db.models import LLMUsageLog
from src.ingestion.extraction import llm_extractor
from src.llm import key_manager, prompt_store
from src.ops.experiments import run_experiment, score
from src.ops.optimization import OptimizationConfig, OptimizationPointer, validate_config
from src.schemas.cv_schema import CVSchema


@pytest.mark.parametrize(
    ("field", "fabricated_item"),
    [
        ("experience", {"company": "Invented employer", "title": "Engineer"}),
        ("projects", {"name": "Invented project"}),
        ("certificates", {"name": "Invented certificate"}),
    ],
)
def test_score_penalizes_fabricated_cv_items(field, fabricated_item):
    expected = CVSchema(full_name="Correct").model_dump(mode="json")
    actual = CVSchema.model_validate({**expected, field: [fabricated_item]}).model_dump(mode="json")

    assert score(expected, expected) == 1.0
    assert score(actual, expected) < 0.85


def test_score_distinguishes_empty_list_from_missing_or_nonempty_list():
    expected = {"name": "Correct", "experience": []}

    assert score(expected, expected) == 1.0
    assert score({"name": "Correct"}, expected) < 1.0
    assert score({"name": "Correct", "experience": [{"company": "Invented"}]}, expected) < 1.0


def test_score_penalizes_extra_items_inside_expected_lists():
    expected = {"projects": [{"name": "Real", "tech_stack": []}]}
    actual = {"projects": [{"name": "Real", "tech_stack": ["Invented"]}, {"name": "Invented"}]}

    assert score(expected, expected) == 1.0
    assert score(actual, expected) < 1.0


def test_score_ignores_unspecified_fields_and_keeps_skills_order_insensitive():
    expected = {"full_name": "Correct", "skills": ["Python", "SQL"]}
    reordered = {"full_name": "Correct", "email": "not specified", "skills": [" sql ", "PYTHON"]}
    invented_skill = {"full_name": "Correct", "skills": ["Python", "SQL", "Invented"]}

    assert score(reordered, expected) == 1.0
    assert score(invented_skill, expected) < 1.0


def test_experiment_pins_each_variant_and_records_versions(monkeypatch):
    # This test measures prompt/version handling, not MySQL advisory locks.
    monkeypatch.setattr("src.ops.locking.ops_lock", lambda key: nullcontext(True))
    engine = create_engine("sqlite://")
    for table in (OptimizationConfig.__table__, OptimizationPointer.__table__, LLMUsageLog.__table__):
        table.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setitem(sys.modules, "src.db.session", types.SimpleNamespace(SessionLocal=factory))
    monkeypatch.setattr(auth, "require_admin", lambda: auth.Identity("admin", "admin", "admin", None))

    proposed = validate_config({"extraction_prompt_version": "deadbeef"})
    with factory() as session:
        session.add(OptimizationPointer(id=1))
        session.add(OptimizationConfig(id="proposal", settings_json=json.dumps(proposed), status="proposed"))
        session.commit()

    example = SimpleNamespace(
        id="example-1", dataset_id="dataset-1",
        inputs={"raw_text": "CV content"}, outputs={"full_name": "Correct"},
    )

    class FakeClient:
        def list_examples(self, dataset_name):
            assert dataset_name == "golden"
            return [example]

        def create_project(self, **kwargs):
            return SimpleNamespace(name=kwargs["project_name"])

    import langsmith

    monkeypatch.setattr(langsmith, "Client", FakeClient)
    monkeypatch.setattr(langsmith, "tracing_context", lambda **kwargs: nullcontext())

    def fake_traceable(**kwargs):
        def decorate(fn):
            def wrapped(*args, **kwargs):
                kwargs.pop("langsmith_extra", None)
                return fn(*args, **kwargs)
            return wrapped
        return decorate

    monkeypatch.setattr(langsmith, "traceable", fake_traceable)
    commits = []

    def fake_get_prompt_text(name, *, commit):
        assert name == "cv-rag-extract-cv"
        commits.append(commit)
        return f"{commit}: {{text}}"

    monkeypatch.setattr(prompt_store, "get_prompt_text", fake_get_prompt_text)
    monkeypatch.setattr(key_manager, "call_with_key_failover", lambda fn: fn("test-key"))
    prompts_used = []

    def fake_extract(api_key, raw_text, model, *, prompt_text):
        prompts_used.append(prompt_text)
        name = "Correct" if prompt_text.startswith("deadbeef:") else "Wrong"
        return CVSchema(full_name=name)

    monkeypatch.setattr(llm_extractor, "_extract_call", fake_extract)

    report = run_experiment("proposal", "golden")

    assert commits == ["55c22bda", "deadbeef"]
    assert prompts_used == ["55c22bda: CV content", "deadbeef: CV content"]
    assert report["baseline_config"]["extraction_prompt_version"] == "55c22bda"
    assert report["proposed_config"]["extraction_prompt_version"] == "deadbeef"
    assert report["results"]["proposal"]["prompt_commit"] == "deadbeef"
    assert report["passed"] is True
    engine.dispose()
