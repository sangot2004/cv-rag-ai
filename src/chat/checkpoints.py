import os

from functools import lru_cache
from langgraph.checkpoint.sqlite import SqliteSaver


@lru_cache(maxsize=1)
def get_checkpointer():
    manager = SqliteSaver.from_conn_string(os.getenv("CHAT_HISTORY_PATH", "chat_history.db"))
    saver = manager.__enter__()

    saver._lifetime_manager = manager
    return saver


def delete_checkpoints(thread_id: str):
    get_checkpointer().delete_thread(thread_id)
