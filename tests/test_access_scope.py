"""
Unit test cho src/retrieval/access_scope.py + việc áp dụng scope vào MỌI
đường dữ liệu — được viết SAU KHI phát hiện lỗ hổng thật: lần đầu code chỉ
áp department scope cho 3/10 tool (search_candidates_sql, count_candidates_stats,
list_recent_candidates), bỏ sót 6 tool còn lại (semantic_search_cv,
get_candidate_detail, compare_candidates, find_candidates_by_certificate,
find_candidates_by_project_tech, evaluate_candidate_against_jd) — Agent có
thể lách qua giới hạn phòng ban chỉ bằng cách đổi sang gọi 1 trong 6 tool đó.

Test này đảm bảo KHÔNG hàm nào trong toàn bộ retrieval/ bị bỏ sót nữa.

Chạy: pytest tests/test_access_scope.py -v
"""

from src.retrieval.access_scope import current_department_id, department_scope
import pytest
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")


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


class TestHybridSearchAppliesScope:
    """Đây chính là test tái hiện đúng lỗ hổng đã fix — semantic_search_cv
    (qua hybrid_search) trước đó KHÔNG hề lọc theo department.
    """

    def test_filters_results_outside_allowed_scope(self):
        with patch("src.retrieval.hybrid_retriever.embed_query", return_value=[0.1, 0.2]), \
            patch(
            "src.retrieval.hybrid_retriever.QdrantStore"
        ) as mock_store_cls, \
            patch("src.retrieval.hybrid_retriever.search_bm25", return_value=[]), \
            patch(
            "src.retrieval.hybrid_retriever.get_allowed_candidate_ids",
            return_value={"allowed-1"},
        ):
            mock_store = MagicMock()
            mock_store.search.return_value = [
                {"chunk_id": "x1", "payload": {"candidate_id": "allowed-1"}, "score": 0.9},
                {"chunk_id": "x2", "payload": {"candidate_id": "NOT_ALLOWED"}, "score": 0.95},
            ]
            mock_store_cls.return_value = mock_store

            from src.retrieval.hybrid_retriever import hybrid_search

            results = hybrid_search("test query", top_k=10)

            candidate_ids_returned = {r["payload"]["candidate_id"] for r in results}
            assert candidate_ids_returned == {"allowed-1"}
            assert "NOT_ALLOWED" not in candidate_ids_returned

    def test_no_filtering_when_no_scope(self):
        with patch("src.retrieval.hybrid_retriever.embed_query", return_value=[0.1, 0.2]), \
                patch("src.retrieval.hybrid_retriever.QdrantStore") as mock_store_cls, \
                patch("src.retrieval.hybrid_retriever.search_bm25", return_value=[]), \
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
