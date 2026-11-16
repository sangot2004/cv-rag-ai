"""BM25 keyword index: tokenizing, Redis round-trip and query ranking (no Redis/Qdrant)."""

import sys
from types import SimpleNamespace

import pytest

from src.retrieval import bm25_index


class FakeRedis:
    def __init__(self):
        self.data = {}

    def set(self, key, value):
        self.data[key] = value

    def get(self, key):
        return self.data.get(key)


@pytest.fixture
def fake_redis(monkeypatch):
    redis_client = FakeRedis()
    monkeypatch.setattr(bm25_index.redis, "from_url", lambda url: redis_client)
    return redis_client


def install_chunks(monkeypatch, chunks):
    class FakeStore:
        def fetch_all_chunks(self):
            return chunks

    monkeypatch.setitem(sys.modules, "src.vectorstore.qdrant_client", SimpleNamespace(QdrantStore=FakeStore))


CHUNKS = [
    {"chunk_id": "c1", "payload": {"chunk_text": "Kinh nghiệm Python Django backend 5 năm", "candidate_id": "a"}},
    {"chunk_id": "c2", "payload": {"chunk_text": "Chuyên viên kế toán thuế báo cáo tài chính", "candidate_id": "b"}},
    {"chunk_id": "c3", "payload": {"chunk_text": "Thiết kế giao diện Figma và UI UX", "candidate_id": "c"}},
    {"chunk_id": "c4", "payload": {"chunk_text": "Quản lý dự án Agile Scrum", "candidate_id": "d"}},
]


def test_tokenize_lowercases_and_keeps_vietnamese_diacritics():
    assert bm25_index._tokenize("Kỹ sư Python, 5 năm!") == ["kỹ", "sư", "python", "5", "năm"]
    assert bm25_index._tokenize("") == []


def test_build_skips_when_there_are_no_chunks(monkeypatch, fake_redis):
    install_chunks(monkeypatch, [])
    assert bm25_index.build_and_store_index() == 0
    assert fake_redis.data == {}


def test_build_stores_index_and_load_returns_it(monkeypatch, fake_redis):
    install_chunks(monkeypatch, CHUNKS)
    assert bm25_index.build_and_store_index() == 4
    assert bm25_index.REDIS_KEY in fake_redis.data
    index = bm25_index.load_index()
    assert index["chunk_ids"] == ["c1", "c2", "c3", "c4"]
    assert index["payloads"][0]["candidate_id"] == "a"


def test_load_returns_none_when_never_built(fake_redis):
    assert bm25_index.load_index() is None


def test_search_without_index_returns_empty(fake_redis):
    assert bm25_index.search_bm25("python") == []


def test_search_ranks_matching_chunk_first(monkeypatch, fake_redis):
    install_chunks(monkeypatch, CHUNKS)
    bm25_index.build_and_store_index()
    results = bm25_index.search_bm25("python django")
    assert results[0]["chunk_id"] == "c1"
    assert results[0]["payload"]["candidate_id"] == "a"
    assert set(results[0]) == {"chunk_id", "score", "payload"}
    assert all(r["score"] > 0 for r in results)


def test_search_drops_zero_score_chunks_and_respects_top_k(monkeypatch, fake_redis):
    install_chunks(monkeypatch, CHUNKS)
    bm25_index.build_and_store_index()
    # Only c2 contains these terms; everything else scores 0 and must be excluded.
    assert [r["chunk_id"] for r in bm25_index.search_bm25("kế toán thuế")] == ["c2"]
    assert bm25_index.search_bm25("từ khóa không tồn tại") == []
    assert len(bm25_index.search_bm25("python figma scrum", top_k=2)) <= 2
