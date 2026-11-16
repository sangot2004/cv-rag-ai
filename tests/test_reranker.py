"""Cross-encoder reranker with a fake model (the real one is a few hundred MB)."""

import pytest

from src.retrieval import reranker


class FakeModel:
    def __init__(self, scores):
        self.scores = scores
        self.pairs = None

    def predict(self, pairs):
        self.pairs = pairs
        return self.scores


def candidates():
    return [
        {"chunk_id": "low", "payload": {"chunk_text": "irrelevant"}},
        {"chunk_id": "high", "payload": {"chunk_text": "python backend"}},
        {"chunk_id": "mid", "payload": {"chunk_text": "some sql"}},
    ]


def test_empty_candidates_never_load_the_model(monkeypatch):
    def boom():
        raise AssertionError("model must not load for empty input")

    monkeypatch.setattr(reranker, "_get_model", boom)
    assert reranker.rerank("python", []) == []


def test_sorts_by_rerank_score_and_attaches_it(monkeypatch):
    model = FakeModel([0.1, 0.9, 0.5])
    monkeypatch.setattr(reranker, "_get_model", lambda: model)
    ranked = reranker.rerank("python backend", candidates(), top_k=5)
    assert [c["chunk_id"] for c in ranked] == ["high", "mid", "low"]
    assert [c["rerank_score"] for c in ranked] == [0.9, 0.5, 0.1]
    assert model.pairs[0] == ("python backend", "irrelevant")


def test_top_k_cuts_the_result(monkeypatch):
    monkeypatch.setattr(reranker, "_get_model", lambda: FakeModel([0.1, 0.9, 0.5]))
    assert [c["chunk_id"] for c in reranker.rerank("q", candidates(), top_k=2)] == ["high", "mid"]


def test_missing_chunk_text_is_scored_as_empty(monkeypatch):
    model = FakeModel([0.3])
    monkeypatch.setattr(reranker, "_get_model", lambda: model)
    reranker.rerank("q", [{"chunk_id": "x", "payload": {}}])
    assert model.pairs == [("q", "")]


def test_model_loads_lazily_once_with_configured_name(monkeypatch):
    created = []

    class FakeCrossEncoder:
        def __init__(self, name):
            created.append(name)

    monkeypatch.setattr(reranker, "CrossEncoder", FakeCrossEncoder)
    monkeypatch.setattr(reranker, "_model", None)
    first = reranker._get_model()
    assert reranker._get_model() is first
    assert created == [reranker.settings.RERANK_MODEL]
