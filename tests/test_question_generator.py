from src.schemas.interview_question_schema import InterviewCategory, InterviewQuestion, QuestionList
import pytest
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")


def make_question(evidence_quote: str, category=InterviewCategory.TECHNICAL) -> InterviewQuestion:
    return InterviewQuestion(
        question="Câu hỏi test",
        category=category,
        cv_section="Dự án",
        evidence_quote=evidence_quote,
    )


class TestNormalizeAndValidateEvidence:
    def test_exact_match(self):
        from src.interview.question_generator import _normalize, _validate_evidence

        cv = _normalize("Implemented Redis caching to improve API performance.")
        q = make_question("Implemented Redis caching to improve API performance.")
        assert _validate_evidence(q, cv) is True

    def test_hallucinated_evidence_rejected(self):
        """Đúng Test Case 4 trong bản kế hoạch — evidence KHÔNG có trong CV
        phải bị phát hiện, không được coi là hợp lệ.
        """
        from src.interview.question_generator import _normalize, _validate_evidence

        cv = _normalize("Used Spring Boot and MySQL for backend development.")
        q = make_question("Built a Kafka pipeline for real-time data processing.")
        assert _validate_evidence(q, cv) is False

    def test_whitespace_and_case_differences_still_match(self):
        """Khác biệt định dạng vô hại (khoảng trắng thừa, hoa/thường)
        KHÔNG được coi là hallucination — chỉ nội dung thật sự khác mới bị loại.
        """
        from src.interview.question_generator import _normalize, _validate_evidence

        cv = _normalize("Implemented Redis caching to improve API performance.")
        q = make_question("IMPLEMENTED   redis caching to improve   api performance.")
        assert _validate_evidence(q, cv) is True

    def test_partial_but_altered_content_rejected(self):
        """Evidence gần giống nhưng bị SỬA NỘI DUNG (không chỉ khác định
        dạng) — vẫn phải bị loại, vì đây chính là dạng hallucination tinh
        vi nhất (AI paraphrase thay vì trích dẫn nguyên văn).
        """
        from src.interview.question_generator import _normalize, _validate_evidence

        cv = _normalize("Implemented Redis caching to improve API performance by 40%.")
        q = make_question("Implemented Memcached caching to improve API performance by 40%.")
        assert _validate_evidence(q, cv) is False


class TestGenerateInterviewQuestions:
    def test_candidate_not_found_raises(self):
        from src.interview.question_generator import CandidateNotFoundError, generate_interview_questions

        with patch("src.interview.question_generator.get_candidate_raw_text", return_value=None):
            with pytest.raises(CandidateNotFoundError):
                generate_interview_questions("nonexistent-id")

    def test_valid_questions_are_saved(self):
        """Câu hỏi có evidence khớp CV phải được lưu và trả về đầy đủ."""
        from src.interview.question_generator import generate_interview_questions

        fake_cv = "Implemented Redis caching to improve API performance."
        fake_result = QuestionList(
            questions=[make_question("Implemented Redis caching to improve API performance.")]
        )

        mock_session = MagicMock()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__enter__.return_value = mock_session

        with patch(
            "src.interview.question_generator.get_candidate_raw_text",
            return_value={"full_name": "A", "raw_text": fake_cv},
        ), patch(
            "src.interview.question_generator.call_with_key_failover", return_value=fake_result
        ), patch("src.interview.question_generator.SessionLocal", return_value=mock_session_ctx):
            result = generate_interview_questions("c1")

            assert len(result) == 1
            assert mock_session.add.called
            assert mock_session.commit.called

    def test_hallucinated_questions_are_filtered_not_saved(self):
        """Bài test quan trọng nhất: câu hỏi hallucination phải bị LOẠI,
        KHÔNG được lưu vào DB, KHÔNG xuất hiện trong kết quả trả về.
        """
        from src.interview.question_generator import generate_interview_questions

        fake_cv = "Used Spring Boot and MySQL for backend development."
        fake_result = QuestionList(
            questions=[
                make_question("Used Spring Boot and MySQL for backend development."),  # thật
                make_question("Built a Kafka pipeline for real-time data processing."),  # bịa
            ]
        )

        mock_session = MagicMock()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__enter__.return_value = mock_session

        with patch(
            "src.interview.question_generator.get_candidate_raw_text",
            return_value={"full_name": "A", "raw_text": fake_cv},
        ), patch(
            "src.interview.question_generator.call_with_key_failover", return_value=fake_result
        ), patch("src.interview.question_generator.SessionLocal", return_value=mock_session_ctx):
            result = generate_interview_questions("c1")

            assert len(result) == 1
            assert "Kafka" not in result[0]["evidence_quote"]
            # add() chỉ được gọi đúng 1 lần (cho câu hợp lệ), không phải 2
            assert mock_session.add.call_count == 1

    def test_all_hallucinated_triggers_retry(self):
        """Nếu TOÀN BỘ câu hỏi lần đầu đều bị loại, hệ thống phải tự thử
        sinh lại 1 lần (không trả về rỗng ngay lập tức nếu retry ra kết
        quả tốt hơn).
        """
        from src.interview.question_generator import generate_interview_questions

        fake_cv = "Used Spring Boot and MySQL for backend development."

        bad_result = QuestionList(questions=[make_question("Hoàn toàn bịa đặt không liên quan")])
        good_result = QuestionList(
            questions=[make_question("Used Spring Boot and MySQL for backend development.")]
        )

        call_count = {"n": 0}

        def fake_call(build_and_call_fn):
            call_count["n"] += 1
            return bad_result if call_count["n"] == 1 else good_result

        mock_session = MagicMock()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__enter__.return_value = mock_session

        with patch(
            "src.interview.question_generator.get_candidate_raw_text",
            return_value={"full_name": "A", "raw_text": fake_cv},
        ), patch(
            "src.interview.question_generator.call_with_key_failover", side_effect=fake_call
        ), patch("src.interview.question_generator.SessionLocal", return_value=mock_session_ctx):
            result = generate_interview_questions("c1")

            assert call_count["n"] == 2  # đã thử lại đúng 1 lần
            assert len(result) == 1
            assert "Spring Boot" in result[0]["evidence_quote"]
