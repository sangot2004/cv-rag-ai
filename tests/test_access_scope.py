"""Department-scoped retrieval regressions using synthetic candidates only."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.models import (
    Base, Candidate, CandidateCertificate, CandidateProject, CandidateSkill,
    Department, IngestionJob, JobPosting,
)
from src.retrieval.access_scope import current_department_id, department_scope


@pytest.fixture
def candidates_db(monkeypatch):
    from src.retrieval import sql_query_tool

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(sql_query_tool, "SessionLocal", factory)

    with factory() as db:
        db.add_all([
            Department(department_id="dept-A", department_name="A"),
            Department(department_id="dept-B", department_name="B"),
            JobPosting(posting_id="posting-A", department_id="dept-A", position_title="Engineer"),
            JobPosting(posting_id="posting-B", department_id="dept-B", position_title="Engineer"),
            IngestionJob(job_id="job", source_type="upload", source_reference="synthetic",
                         minio_bucket="test", minio_object_key="test", original_filename="test.pdf",
                         file_type="pdf"),
        ])
        db.flush()
        db.add_all([
            Candidate(candidate_id="local", full_name="Local", posting_id="posting-A", source_job_id="job"),
            Candidate(candidate_id="foreign", full_name="Foreign", posting_id="posting-B", source_job_id="job"),
            Candidate(candidate_id="unassigned", full_name="Unassigned", source_job_id="job"),
        ])
        db.flush()
        for candidate_id in ("local", "foreign", "unassigned"):
            db.add_all([
                CandidateCertificate(candidate_id=candidate_id, name="AWS Certified"),
                CandidateProject(candidate_id=candidate_id, name="Demo", tech_stack="Kubernetes"),
                CandidateSkill(candidate_id=candidate_id, skill_name="Python developer"),
            ])
        db.commit()

    yield sql_query_tool
    engine.dispose()


class TestDepartmentScope:
    def test_default_is_none_no_restriction(self):
        assert current_department_id.get() is None

    def test_scope_sets_and_resets(self):
        with department_scope("dept-A"):
            assert current_department_id.get() == "dept-A"
        assert current_department_id.get() is None

    def test_nested_scope_restores_outer_value(self):
        with department_scope("dept-A"):
            with department_scope("dept-B"):
                assert current_department_id.get() == "dept-B"
            assert current_department_id.get() == "dept-A"
        assert current_department_id.get() is None

    def test_scope_resets_even_on_exception(self):
        """Nếu code bên trong raise lỗi, scope vẫn phải reset đúng — không
        để rò rỉ giới hạn department sang request tiếp theo dùng chung
        process (vd request sau vô tình không set scope, lẽ ra phải thấy
        None nhưng lại còn sót giá trị cũ).
        """
        with pytest.raises(ValueError):
            with department_scope("dept-A"):
                raise ValueError("lỗi giả lập")
        assert current_department_id.get() is None


class TestGetAllowedCandidateIds:
    def test_none_when_no_scope(self):
        from src.retrieval.sql_query_tool import get_allowed_candidate_ids

        with department_scope(None):
            assert get_allowed_candidate_ids() is None

    def test_returns_set_when_scope_active(self):
        from src.retrieval.sql_query_tool import get_allowed_candidate_ids

        mock_session = MagicMock()
        mock_session.execute.return_value.all.return_value = [("c1",), ("c2",)]
        mock_session_ctx = MagicMock()
        mock_session_ctx.__enter__.return_value = mock_session

        with department_scope("dept-A"), patch(
            "src.retrieval.sql_query_tool.SessionLocal", return_value=mock_session_ctx
        ):
            result = get_allowed_candidate_ids()
            assert result == {"c1", "c2"}


@pytest.mark.parametrize(
    ("method", "term"),
    [("search_by_certificate", "AWS"), ("search_by_project_tech", "Kubernetes")],
)
def test_specialized_queries_restrict_department_and_limit(candidates_db, method, term):
    search = getattr(candidates_db, method)
    with department_scope("dept-A"):
        assert {r["candidate_id"] for r in search(term, limit=1)} == {"local"}
    with department_scope("dept-B"):
        assert {r["candidate_id"] for r in search(term, limit=1)} == {"foreign"}
    with department_scope(None):
        assert {r["candidate_id"] for r in search(term)} == {"local", "foreign", "unassigned"}


def test_skill_count_matches_substring_search_within_department(candidates_db):
    with department_scope("dept-A"):
        assert candidates_db.count_candidate_stats(skills=["Python"])["count"] == 1
        assert {r["candidate_id"] for r in candidates_db.search_candidates_sql(skills=["Python"])} == {"local"}


class TestHybridSearchAppliesScope:
    """Đây chính là test tái hiện đúng lỗ hổng đã fix — semantic_search_cv
    (qua hybrid_search) trước đó KHÔNG hề lọc theo department.
    """

    def test_filters_results_outside_allowed_scope(self):
        with patch("src.retrieval.hybrid_retriever.embed_query", return_value=[0.1, 0.2]), \
            patch("src.retrieval.hybrid_retriever.QdrantStore") as mock_store_cls, \
            patch("src.retrieval.hybrid_retriever.load_index", return_value=None), \
            patch("src.ops.optimization.active_config", return_value={"retrieval_multiplier": 2}), \
            patch(
            "src.retrieval.hybrid_retriever.get_allowed_candidate_ids",
            return_value={"allowed-1"},
        ):
            mock_store = MagicMock()
            mock_store.collection = "test"
            mock_store.client.query_points.return_value.points = [
                SimpleNamespace(id="x1", payload={"candidate_id": "allowed-1"}, score=0.9),
                SimpleNamespace(id="x2", payload={"candidate_id": "NOT_ALLOWED"}, score=0.95),
            ]
            mock_store_cls.return_value = mock_store

            from src.retrieval.hybrid_retriever import hybrid_search

            results = hybrid_search("test query", top_k=10)

            candidate_ids_returned = {r["payload"]["candidate_id"] for r in results}
            assert candidate_ids_returned == {"allowed-1"}
            assert "NOT_ALLOWED" not in candidate_ids_returned
            query_filter = mock_store.client.query_points.call_args.kwargs["query_filter"]
            assert query_filter.must[0].match.any == ["allowed-1"]

    def test_local_hit_survives_foreign_hit_above_top_k(self):
        with patch("src.retrieval.hybrid_retriever.embed_query", return_value=[0.1]), \
            patch("src.retrieval.hybrid_retriever.QdrantStore") as mock_store_cls, \
            patch("src.retrieval.hybrid_retriever.load_index", return_value=None), \
            patch("src.retrieval.hybrid_retriever.get_allowed_candidate_ids", return_value={"local"}), \
            patch("src.ops.optimization.active_config", return_value={"retrieval_multiplier": 2}):
            mock_store = mock_store_cls.return_value
            mock_store.collection = "test"
            mock_store.client.query_points.return_value.points = [
                SimpleNamespace(id="foreign-chunk", payload={"candidate_id": "foreign"}, score=0.99),
                SimpleNamespace(id="local-chunk", payload={"candidate_id": "local"}, score=0.98),
            ]
            from src.retrieval.hybrid_retriever import hybrid_search

            results = hybrid_search("test query", top_k=1)
            assert [r["chunk_id"] for r in results] == ["local-chunk"]
            assert mock_store.client.query_points.call_args.kwargs["query_filter"].must[0].match.any == ["local"]

    def test_bm25_ranks_permitted_chunks_before_limit(self):
        index = {
            "bm25": SimpleNamespace(get_scores=lambda _: [10, 9, 8]),
            "chunk_ids": ["foreign-1", "foreign-2", "local-chunk"],
            "payloads": [
                {"candidate_id": "foreign"},
                {"candidate_id": "foreign"},
                {"candidate_id": "local"},
            ],
        }
        with patch("src.retrieval.hybrid_retriever.embed_query", return_value=[0.1]), \
            patch("src.retrieval.hybrid_retriever.QdrantStore") as mock_store_cls, \
            patch("src.retrieval.hybrid_retriever.load_index", return_value=index), \
            patch("src.retrieval.hybrid_retriever.get_allowed_candidate_ids", return_value={"local"}), \
            patch("src.ops.optimization.active_config", return_value={"retrieval_multiplier": 2}):
            mock_store_cls.return_value.client.query_points.return_value.points = []
            from src.retrieval.hybrid_retriever import hybrid_search

            results = hybrid_search("test query", top_k=1)
            assert [r["chunk_id"] for r in results] == ["local-chunk"]

    def test_no_filtering_when_no_scope(self):
        with patch("src.retrieval.hybrid_retriever.embed_query", return_value=[0.1, 0.2]), \
                patch("src.retrieval.hybrid_retriever.QdrantStore") as mock_store_cls, \
                patch("src.retrieval.hybrid_retriever.search_bm25", return_value=[]), \
                patch("src.ops.optimization.active_config", return_value={"retrieval_multiplier": 2}), \
                patch("src.retrieval.hybrid_retriever.get_allowed_candidate_ids", return_value=None):
            mock_store = MagicMock()
            mock_store.search.return_value = [
                {"chunk_id": "x1", "payload": {"candidate_id": "c1"}, "score": 0.9},
                {"chunk_id": "x2", "payload": {"candidate_id": "c2"}, "score": 0.8},
            ]
            mock_store_cls.return_value = mock_store

            from src.retrieval.hybrid_retriever import hybrid_search

            results = hybrid_search("test query", top_k=10)
            assert len(results) == 2  # không bị lọc gì khi get_allowed_candidate_ids() trả None


class TestGetCandidateFullProfileAppliesScope:
    def test_blocked_candidate_returns_none_not_error(self):
        """Candidate CÓ tồn tại nhưng ở department khác -> phải trả về
        None GIỐNG HỆT trường hợp không tồn tại, không phân biệt 2 lý do
        (tránh lộ thông tin candidate_id này có tồn tại hay không).
        """
        mock_candidate = MagicMock()
        mock_candidate.posting.department_id = "OTHER_DEPT"

        mock_session = MagicMock()
        mock_session.get.return_value = mock_candidate
        mock_session_ctx = MagicMock()
        mock_session_ctx.__enter__.return_value = mock_session

        with department_scope("dept-A"), patch(
            "src.retrieval.sql_query_tool.SessionLocal", return_value=mock_session_ctx
        ):
            from src.retrieval.sql_query_tool import get_candidate_full_profile

            result = get_candidate_full_profile("some-id")
            assert result is None

    def test_candidate_without_posting_blocked_when_scope_active(self):
        """Candidate chưa được gán posting_id nào (posting=None) -> khi có
        scope active, PHẢI từ chối (không đủ thông tin để xác nhận thuộc
        đúng department) — an toàn hơn là mặc định cho qua.
        """
        mock_candidate = MagicMock()
        mock_candidate.posting = None

        mock_session = MagicMock()
        mock_session.get.return_value = mock_candidate
        mock_session_ctx = MagicMock()
        mock_session_ctx.__enter__.return_value = mock_session

        with department_scope("dept-A"), patch(
            "src.retrieval.sql_query_tool.SessionLocal", return_value=mock_session_ctx
        ):
            from src.retrieval.sql_query_tool import get_candidate_full_profile

            result = get_candidate_full_profile("some-id")
            assert result is None
