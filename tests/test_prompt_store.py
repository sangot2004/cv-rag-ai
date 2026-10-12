from types import SimpleNamespace

import pytest
from langchain_core.prompts import PromptTemplate

from src.llm import prompt_store


@pytest.fixture(autouse=True)
def clear_prompt_cache():
    prompt_store._pull_template.cache_clear()
    yield
    prompt_store._pull_template.cache_clear()


def test_prompt_store_uses_pinned_commit_and_caches_pull(monkeypatch):
    calls = []

    def pull_prompt(identifier):
        calls.append(identifier)
        prompt = PromptTemplate.from_template("Hello {candidate_name}: {position}; {interview_details}")
        prompt.metadata = {"lc_hub_commit_hash": "5a7c8235-more-hash"}
        return prompt

    monkeypatch.setattr(prompt_store, "_get_client", lambda: SimpleNamespace(pull_prompt=pull_prompt))

    name = "cv-rag-draft-interview-email"
    assert prompt_store.format_prompt(
        name, candidate_name="Lan", position="Engineer", interview_details="10:00"
    ) == "Hello Lan: Engineer; 10:00"
    assert prompt_store.get_prompt_text(name).startswith("Hello ")
    assert calls == ["cv-rag-draft-interview-email:5a7c8235"]


def test_prompt_store_rejects_mutable_revision_and_wrong_commit(monkeypatch):
    name = "cv-rag-agent-system"
    calls = []

    def pull_prompt(identifier):
        calls.append(identifier)
        prompt = PromptTemplate.from_template("system")
        prompt.metadata = {"lc_hub_commit_hash": "deadbeef-other-hash"}
        return prompt

    monkeypatch.setattr(prompt_store, "_get_client", lambda: SimpleNamespace(pull_prompt=pull_prompt))

    with pytest.raises(ValueError, match="immutable commit"):
        prompt_store.get_prompt_text(name, commit="latest")
    assert calls == []
    with pytest.raises(ValueError, match="returned commit"):
        prompt_store.get_prompt_text(name)
    assert calls == ["cv-rag-agent-system:73398ad0"]


def test_prompt_store_rejects_changed_template_variables(monkeypatch):
    prompt = PromptTemplate.from_template("Hello {candidate_name}")
    monkeypatch.setattr(
        prompt_store,
        "_get_client",
        lambda: SimpleNamespace(pull_prompt=lambda _: prompt),
    )

    with pytest.raises(ValueError, match="variables"):
        prompt_store.get_prompt_text("cv-rag-draft-interview-email")
