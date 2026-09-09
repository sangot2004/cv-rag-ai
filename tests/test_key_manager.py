"""
Unit test cho src/llm/key_manager.py — logic quan trọng, dễ hỏng âm thầm
(sai 1 chỗ là toàn bộ hệ thống không failover đúng khi hết quota, mà
không có triệu chứng rõ ràng nào ngay lập tức để phát hiện).

Chạy: pytest tests/test_key_manager.py -v
"""

from src.llm.key_manager import ApiKeyManager, call_with_key_failover, is_quota_error
import pytest
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")


class FakeQuotaError(Exception):
    code = 429


class FakeOtherError(Exception):
    pass


@pytest.fixture
def fake_redis():
    """Redis giả lập bằng dict Python — đủ để test logic đọc/ghi index,
    không cần Redis server thật.
    """
    store: dict[str, int] = {}
    mock_client = MagicMock()
    mock_client.get.side_effect = lambda k: store.get(k)
    mock_client.set.side_effect = lambda k, v: store.__setitem__(k, v)
    return mock_client, store


class TestIsQuotaError:
    def test_detect_by_code_429(self):
        assert is_quota_error(FakeQuotaError()) is True

    def test_detect_by_message_text(self):
        assert is_quota_error(Exception("429 RESOURCE_EXHAUSTED: quota exceeded")) is True

    def test_not_quota_error(self):
        assert is_quota_error(FakeOtherError("model not found")) is False


class TestApiKeyManager:
    def test_requires_at_least_one_key(self, fake_redis):
        mock_client, _ = fake_redis
        with patch("src.llm.key_manager.redis.from_url", return_value=mock_client):
            with pytest.raises(ValueError):
                ApiKeyManager([], "redis://fake")

    def test_starts_at_first_key(self, fake_redis):
        mock_client, _ = fake_redis
        with patch("src.llm.key_manager.redis.from_url", return_value=mock_client):
            manager = ApiKeyManager(["keyA", "keyB"], "redis://fake")
            assert manager.get_current_key() == "keyA"

    def test_mark_exhausted_moves_to_next_key(self, fake_redis):
        mock_client, _ = fake_redis
        with patch("src.llm.key_manager.redis.from_url", return_value=mock_client):
            manager = ApiKeyManager(["keyA", "keyB", "keyC"], "redis://fake")
            manager.mark_exhausted()
            assert manager.get_current_key() == "keyB"

    def test_mark_exhausted_wraps_around(self, fake_redis):
        mock_client, _ = fake_redis
        with patch("src.llm.key_manager.redis.from_url", return_value=mock_client):
            manager = ApiKeyManager(["keyA", "keyB"], "redis://fake")
            manager.mark_exhausted()
            manager.mark_exhausted()
            assert manager.get_current_key() == "keyA"  # quay lại đầu

    def test_shared_redis_syncs_across_instances(self, fake_redis):
        """Bài test quan trọng nhất — mô phỏng đúng vấn đề đã fix: 2
        'worker' (2 instance ApiKeyManager riêng) dùng CHUNG 1 Redis phải
        thấy thay đổi của nhau ngay lập tức.
        """
        mock_client, _ = fake_redis
        with patch("src.llm.key_manager.redis.from_url", return_value=mock_client):
            worker_a = ApiKeyManager(["keyA", "keyB", "keyC"], "redis://fake")
            worker_b = ApiKeyManager(["keyA", "keyB", "keyC"], "redis://fake")

            assert worker_a.get_current_key() == worker_b.get_current_key() == "keyA"

            worker_a.mark_exhausted()

            # worker_b KHÔNG hề gọi mark_exhausted(), nhưng phải thấy key
            # đã đổi vì đọc chung Redis — đây là hành vi CHƯA có ở bản cũ
            # (mỗi process có index riêng trong biến local).
            assert worker_b.get_current_key() == "keyB"

    def test_redis_read_failure_falls_back_to_index_zero(self, fake_redis):
        """Nếu Redis tạm thời lỗi, không được để cả hệ thống crash — chấp
        nhận fallback về key #0 thay vì raise exception.
        """
        mock_client, _ = fake_redis
        mock_client.get.side_effect = Exception("Redis connection lost")
        with patch("src.llm.key_manager.redis.from_url", return_value=mock_client):
            manager = ApiKeyManager(["keyA", "keyB"], "redis://fake")
            assert manager.get_current_key() == "keyA"  # không crash


class TestCallWithKeyFailover:
    def test_success_on_first_try(self, fake_redis):
        mock_client, _ = fake_redis
        with patch("src.llm.key_manager.redis.from_url", return_value=mock_client):
            with patch("src.llm.key_manager._manager", None):
                import src.llm.key_manager as km

                km._manager = ApiKeyManager(["keyA"], "redis://fake")
                result = call_with_key_failover(lambda key: f"ok-{key}")
                assert result == "ok-keyA"

    def test_failover_to_second_key_on_quota_error(self, fake_redis):
        mock_client, _ = fake_redis
        with patch("src.llm.key_manager.redis.from_url", return_value=mock_client):
            import src.llm.key_manager as km

            km._manager = ApiKeyManager(["keyA", "keyB"], "redis://fake")

            call_log = []

            def fake_call(key):
                call_log.append(key)
                if key == "keyA":
                    raise FakeQuotaError("quota exceeded")
                return f"success-{key}"

            result = call_with_key_failover(fake_call)
            assert result == "success-keyB"
            assert call_log == ["keyA", "keyB"]

    def test_non_quota_error_raises_immediately_no_failover(self, fake_redis):
        """Lỗi KHÔNG phải quota (vd sai model name) không nên đổi key —
        đổi key cũng không giải quyết được gì, chỉ tốn thêm 1 lần gọi lỗi.
        """
        mock_client, _ = fake_redis
        with patch("src.llm.key_manager.redis.from_url", return_value=mock_client):
            import src.llm.key_manager as km

            km._manager = ApiKeyManager(["keyA", "keyB"], "redis://fake")

            call_log = []

            def fake_call(key):
                call_log.append(key)
                raise FakeOtherError("model not found")

            with pytest.raises(FakeOtherError):
                call_with_key_failover(fake_call)

            assert call_log == ["keyA"]  # không thử sang keyB

    def test_all_keys_exhausted_raises_last_error(self, fake_redis):
        mock_client, _ = fake_redis
        with patch("src.llm.key_manager.redis.from_url", return_value=mock_client):
            import src.llm.key_manager as km

            km._manager = ApiKeyManager(["keyA", "keyB"], "redis://fake")

            def always_quota_error(key):
                raise FakeQuotaError(f"quota exceeded for {key}")

            with pytest.raises(FakeQuotaError):
                call_with_key_failover(always_quota_error)
