import os
import sqlite3
from pathlib import Path
from threading import RLock

from langgraph.checkpoint.sqlite import SqliteSaver

_lock = RLock()
_saver = None
_reader = None
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def history_path() -> Path:
    path = Path(os.getenv("CHAT_HISTORY_PATH", "chat_history.db")).expanduser()
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def get_checkpointer():
    global _saver
    with _lock:
        if _saver is None:
            path = history_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            _saver = SqliteSaver(sqlite3.connect(str(path), check_same_thread=False, timeout=30))
        return _saver


def close_checkpointer():
    """Call only after all in-flight requests have drained."""
    global _saver, _reader
    with _lock:
        if _saver is not None:
            _saver.conn.close()
        _saver = _reader = None


def read_state(thread_id):
    """Read the same graph topology without a provider or remote prompt."""
    global _reader
    saver = get_checkpointer()
    with _lock:
        if _reader is None or _reader.checkpointer is not saver:
            from src.agent.agent_executor import build_agent_executor
            _reader = build_agent_executor(None, checkpointer=saver, read_only=True)
        reader = _reader
    return reader.get_state({"configurable": {"thread_id": thread_id}})


def delete_checkpoints(thread_id: str):
    get_checkpointer().delete_thread(thread_id)
