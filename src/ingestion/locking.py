"""MySQL advisory locks span the model/object-store work without a DB row lease.

SQLite is only used by offline tests; its fallback coordinates local threads.
Production ingestion intentionally runs one pipeline at a time for text dedupe.
"""
from contextlib import contextmanager
from hashlib import sha256
from threading import Lock
from weakref import WeakValueDictionary
from sqlalchemy import text
from src.db import session as database

_guard = Lock()
_locks = WeakValueDictionary()


@contextmanager
def named_lock(key):
    name = "cv:" + sha256(key.encode()).hexdigest()[:60]
    with database.SessionLocal() as db:
        if db.get_bind().dialect.name == "mysql":
            acquired = db.scalar(text("SELECT GET_LOCK(:name, 0)"), {"name": name}) == 1
            try:
                yield acquired
            finally:
                if acquired:
                    db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": name})
        else:
            with _guard:
                lock = _locks.setdefault(name, Lock())
            acquired = lock.acquire(blocking=False)
            try:
                yield acquired
            finally:
                if acquired:
                    lock.release()
