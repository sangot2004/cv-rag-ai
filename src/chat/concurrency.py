"""Process-local coordination. Run one writer process for the checkpoint DB."""
from contextlib import contextmanager
from threading import Lock, RLock

from src.chat.errors import ChatConflict

_guard = Lock()
_locks = {}
_running = set()


@contextmanager
def conversation_lock(thread_id: str, *, execution: bool = False):
    # Refcounts include contenders, so a lock cannot disappear while in use.
    with _guard:
        lock, users = _locks.get(thread_id, (RLock(), 0))
        _locks[thread_id] = (lock, users + 1)
    acquired = lock.acquire(blocking=False)
    try:
        if not acquired:
            raise ChatConflict("CONVERSATION_BUSY", "Hội thoại đang được xử lý. Hãy đọc lại trạng thái.")
        if execution:
            with _guard:
                _running.add(thread_id)
        yield
    finally:
        if acquired:
            if execution:
                with _guard:
                    _running.discard(thread_id)
            lock.release()
        with _guard:
            remaining = _locks[thread_id][1] - 1
            if remaining:
                _locks[thread_id] = (lock, remaining)
            else:
                del _locks[thread_id]


def is_running(thread_id: str) -> bool:
    with _guard:
        return thread_id in _running
