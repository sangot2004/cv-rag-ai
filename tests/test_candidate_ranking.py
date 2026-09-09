from src.schemas.jd_schema import JDSchema
import pytest
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")


def make_jd(**overrides) -> JDSchema:
    defaults = {
        "position_title": "Data Engineer",
        "required_skills": ["Python"],
        "min_years_experience": 2.0,
        "raw_text": "Cần Data Engineer biết Python, SQL, 2 năm kinh nghiệm.",
    }
    defaults.update(overrides)
    return JDSchema(**defaults)


class TestRankCandidatesForJD:
    def test_empty_when_sql_prefilter_returns_nothing(self):
        """Nếu không candidate nào khớp tiêu chí cứng của JD, trả về rỗng
        ngay — KHÔNG được gọi tiếp hybrid_search/evaluate (tốn quota vô ích).
        """
        with patch("src.retrieval.candidate_ranking.search_candidates_sql", return_value=[]), \
                patch("src.retrieval.candidate_ranking.hybrid_search") as mock_hybrid, \
                patch("src.retrieval.candidate_ranking.evaluate_candidate") as mock_eval:
            from src.retrieval.candidate_ranking import rank_candidates_for_jd

            result = rank_candidates_for_jd(make_jd(), top_k=5)

            assert result == []
            mock_hybrid.assert_not_called()
            mock_eval.assert_not_called()

    def test_empty_when_semantic_search_matches_nothing_in_pool(self):
        """SQL prefilter có kết quả, nhưng hybrid_search không trả về chunk
        nào thuộc pool đã lọc (candidate_id không khớp) -> vẫn phải trả rỗng
        một cách an toàn, không crash, không gọi evaluate.
        """
        with patch(
            "src.retrieval.candidate_ranking.search_candidates_sql",
            return_value=[{"candidate_id": "c1", "full_name": "A"}],
        ), patch(
            "src.retrieval.candidate_ranking.hybrid_search",
            return_value=[{"chunk_id": "x1", "payload": {"candidate_id": "OTHER_ID"}, "score": 0.9}],
        ), patch("src.retrieval.candidate_ranking.evaluate_candidate") as mock_eval:
            from src.retrieval.candidate_ranking import rank_candidates_for_jd

            result = rank_candidates_for_jd(make_jd(), top_k=5)

            assert result == []
            mock_eval.assert_not_called()

    def test_full_flow_ranks_by_overall_score(self):
        """Luồng đầy đủ: 2 candidate qua hết 3 bước, kết quả phải sắp theo
        overall_score giảm dần — kể cả khi thứ tự retrieval_score không
        trùng thứ tự overall_score (rubric evaluate mới là điểm quyết định
        cuối cùng, không phải điểm retrieval).
        """
        sql_result = [
            {"candidate_id": "c1", "full_name": "A"},
            {"candidate_id": "c2", "full_name": "B"},
        ]
        hybrid_result = [
            {"chunk_id": "x1", "payload": {"candidate_id": "c1"}, "score": 0.5},
            {"chunk_id": "x2", "payload": {"candidate_id": "c2"}, "score": 0.9},
        ]
        # rerank trả về với rerank_score — c2 cao hơn c1 ở bước retrieval
        reranked_result = [
            {"chunk_id": "x2", "payload": {"candidate_id": "c2"}, "rerank_score": 0.95},
            {"chunk_id": "x1", "payload": {"candidate_id": "c1"}, "rerank_score": 0.60},
        ]

        class FakeEval:
            def __init__(self, candidate_id, overall_score):
                self.candidate_id = candidate_id
                self.overall_score = overall_score

            def model_dump(self):
                return {"candidate_id": self.candidate_id, "overall_score": self.overall_score, "summary": "ok"}

        # NGƯỢC lại với thứ tự retrieval: c1 chấm điểm rubric CAO hơn c2,
        # dù retrieval xếp c2 lên trước -> kết quả cuối phải theo overall_score
        eval_results = {
            "c1": FakeEval("c1", overall_score=4.5),
            "c2": FakeEval("c2", overall_score=3.0),
        }

        with patch("src.retrieval.candidate_ranking.search_candidates_sql", return_value=sql_result), \
            patch("src.retrieval.candidate_ranking.hybrid_search", return_value=hybrid_result), \
            patch("src.retrieval.candidate_ranking.rerank", return_value=reranked_result), \
            patch(
            "src.retrieval.candidate_ranking.evaluate_candidate",
            side_effect=lambda cid, jd_text: eval_results[cid],
        ):
            from src.retrieval.candidate_ranking import rank_candidates_for_jd

            result = rank_candidates_for_jd(make_jd(), top_k=5)

            assert len(result) == 2
            # c1 phải đứng đầu vì overall_score cao hơn, DÙ retrieval xếp c2 trước
            assert result[0]["candidate_id"] == "c1"
            assert result[1]["candidate_id"] == "c2"

    def test_top_k_is_capped_at_max(self):
        """top_k truyền vào lớn hơn MAX_TOP_K phải bị giới hạn lại, không
        được gọi evaluate_candidate nhiều hơn MAX_TOP_K lần (chặn tốn quota
        quá mức — đúng lý do MAX_TOP_K tồn tại).
        """
        from src.retrieval.candidate_ranking import MAX_TOP_K

        sql_result = [{"candidate_id": f"c{i}", "full_name": f"Name{i}"} for i in range(20)]
        hybrid_result = [
            {"chunk_id": f"x{i}", "payload": {"candidate_id": f"c{i}"}, "score": 0.5}
            for i in range(20)
        ]
        reranked_result = [
            {"chunk_id": f"x{i}", "payload": {"candidate_id": f"c{i}"}, "rerank_score": 1.0 - i * 0.01}
            for i in range(20)
        ]

        eval_call_count = {"n": 0}

        def fake_evaluate(cid, jd_text):
            eval_call_count["n"] += 1
            mock_result = MagicMock()
            mock_result.candidate_id = cid
            mock_result.overall_score = 3.0
            mock_result.model_dump.return_value = {"candidate_id": cid, "overall_score": 3.0}
            return mock_result

        with patch("src.retrieval.candidate_ranking.search_candidates_sql", return_value=sql_result), \
                patch("src.retrieval.candidate_ranking.hybrid_search", return_value=hybrid_result), \
                patch("src.retrieval.candidate_ranking.rerank", return_value=reranked_result), \
                patch("src.retrieval.candidate_ranking.evaluate_candidate", side_effect=fake_evaluate):
            from src.retrieval.candidate_ranking import rank_candidates_for_jd

            result = rank_candidates_for_jd(make_jd(), top_k=999)  # cố tình truyền vượt mức

            assert eval_call_count["n"] <= MAX_TOP_K
            assert len(result) <= MAX_TOP_K

    def test_evaluate_returning_none_is_skipped_not_crashed(self):
        """evaluate_candidate() có thể trả None (candidate_id không tồn tại
        — hiếm khi xảy ra ở đây vì đã qua SQL prefilter, nhưng vẫn nên xử
        lý an toàn) — không được để crash cả hàm.
        """
        sql_result = [{"candidate_id": "c1", "full_name": "A"}]
        hybrid_result = [{"chunk_id": "x1", "payload": {"candidate_id": "c1"}, "score": 0.5}]
        reranked_result = [{"chunk_id": "x1", "payload": {"candidate_id": "c1"}, "rerank_score": 0.9}]

        with patch("src.retrieval.candidate_ranking.search_candidates_sql", return_value=sql_result), \
                patch("src.retrieval.candidate_ranking.hybrid_search", return_value=hybrid_result), \
                patch("src.retrieval.candidate_ranking.rerank", return_value=reranked_result), \
                patch("src.retrieval.candidate_ranking.evaluate_candidate", return_value=None):
            from src.retrieval.candidate_ranking import rank_candidates_for_jd

            result = rank_candidates_for_jd(make_jd(), top_k=5)

            assert result == []  # bị skip an toàn, không crash
