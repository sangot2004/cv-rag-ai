import logging
import threading
import redis

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

REDIS_INDEX_KEY = "gemini_key_manager:current_index"


def is_quota_error(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if code == 429:
        return True

    status = str(getattr(exc, "status", "")).upper()
    if "RESOURCE_EXHAUSTED" in status:
        return True

    text = str(exc).lower()
    return "429" in text or "resource_exhausted" in text or "quota" in text


class ApiKeyManager:
    def __init__(self, keys: list[str], redis_url: str):
        if not keys:
            raise ValueError("Cần ít nhất 1 GOOGLE_API_KEY trong .env")
        self._keys = keys
        self._lock = threading.Lock()
        self._redis = redis.from_url(redis_url)

    @property
    def num_keys(self) -> int:
        return len(self._keys)

    def _get_index(self) -> int:
        try:
            raw = self._redis.get(REDIS_INDEX_KEY)
            if raw is None:
                return 0
            return int(raw) % len(self._keys)
        except Exception:
            logger.exception("Không đọc được index từ Redis, fallback về key #0")
            return 0

    def get_current_key(self) -> str:
        with self._lock:
            return self._keys[self._get_index()]

    def mark_exhausted(self) -> None:
        with self._lock:
            old_index = self._get_index()
            new_index = (old_index + 1) % len(self._keys)
            try:
                self._redis.set(REDIS_INDEX_KEY, new_index)
            except Exception:
                logger.exception("Không ghi được index mới vào Redis (key vẫn đổi tạm trong process)")
            logger.warning(
                "Key #%d hết quota, chuyển sang key #%d (tổng %d key, đồng bộ qua Redis)",
                old_index, new_index, len(self._keys),
            )


_manager: ApiKeyManager | None = None


def get_key_manager() -> ApiKeyManager:
    global _manager
    if _manager is None:
        settings = get_settings()
        _manager = ApiKeyManager(settings.GOOGLE_API_KEYS, settings.REDIS_URL)
    return _manager


def call_with_key_failover(build_and_call_fn):
    """Chạy build_and_call_fn(api_key) — thử lần lượt từng key, chuyển key
    kế tiếp khi gặp lỗi quota, dừng lại re-raise nếu đã thử hết toàn bộ key
    mà vẫn lỗi (hoặc lỗi không phải do quota — không có ý nghĩa gì để đổi
    key trong trường hợp đó, vd lỗi sai model name).
    """
    manager = get_key_manager()
    last_error: Exception | None = None

    for attempt in range(manager.num_keys):
        key = manager.get_current_key()
        try:
            return build_and_call_fn(key)
        except Exception as e:
            last_error = e
            if is_quota_error(e) and attempt < manager.num_keys - 1:
                manager.mark_exhausted()
                continue
            raise

    raise last_error
