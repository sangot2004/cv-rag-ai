from contextlib import contextmanager
from contextvars import ContextVar


current_department_id: ContextVar[str | None] = ContextVar("current_department_id", default=None)


@contextmanager
def department_scope(department_id: str | None):
    token = current_department_id.set(department_id)
    try:
        yield
    finally:
        current_department_id.reset(token)
