from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from src.ingestion.locking import named_lock

_held = ContextVar("ops_locks", default=frozenset())


@contextmanager
def ops_lock(key):
    if key in _held.get():
        yield True
        return
    with named_lock(key) as acquired:
        token = _held.set(_held.get() | {key}) if acquired else None
        try:
            yield acquired
        finally:
            if token is not None:
                _held.reset(token)


def serialized(fn):
    @wraps(fn)
    def wrapped(identifier=None, *args, **kwargs):
        with ops_lock("ops:" + str(identifier)) as acquired:
            if not acquired:
                raise ValueError("Optimization operation already running")
            return fn(identifier, *args, **kwargs)
    return wrapped
