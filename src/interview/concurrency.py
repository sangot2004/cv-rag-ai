"""Per-candidate coordination for the single API writer process."""
from contextlib import contextmanager
from threading import Lock

from src.interview.errors import InterviewConflict

_guard = Lock()
_locks = {}
_generating = set()


@contextmanager
def interview_lock(candidate_id, *, generating=False):
    with _guard:
        lock, users = _locks.get(candidate_id, (Lock(), 0))
        _locks[candidate_id] = (lock, users + 1)
    acquired = lock.acquire(blocking=False)
    try:
        if not acquired:
            raise InterviewConflict("INTERVIEW_BUSY", "Bộ câu hỏi đang được xử lý. Hãy tải lại trạng thái.")
        if generating:
            with _guard:
                _generating.add(candidate_id)
        yield
    finally:
        if acquired:
            with _guard:
                _generating.discard(candidate_id)
            lock.release()
        with _guard:
            remaining = _locks[candidate_id][1] - 1
            if remaining:
                _locks[candidate_id] = (lock, remaining)
            else:
                del _locks[candidate_id]


def is_generating(candidate_id):
    with _guard:
        return candidate_id in _generating
