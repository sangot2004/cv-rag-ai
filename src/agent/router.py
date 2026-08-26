import logging

from langgraph.checkpoint.memory import InMemorySaver

from src.agent.agent_executor import build_agent_executor
from src.llm.key_manager import get_key_manager, is_quota_error

logger = logging.getLogger(__name__)

_checkpointer = InMemorySaver()
_graph = None
_graph_key: str | None = None


def _get_graph():
    """Lazy build — tránh khởi tạo LLM client lúc import module."""
    global _graph, _graph_key
    current_key = get_key_manager().get_current_key()
    if _graph is None or _graph_key != current_key:
        _graph = build_agent_executor(current_key, checkpointer=_checkpointer)
        _graph_key = current_key
    return _graph


def ask(question: str, thread_id: str = "default") -> str:
    """Entrypoint duy nhất cho Luồng C — nhận câu hỏi tiếng Việt tự nhiên,
    Agent tự quyết định gọi tool nào qua tool-calling của Gemini.
    thread_id: định danh phiên hội thoại — cùng thread_id thì Agent nhớ
    được các câu hỏi/trả lời trước đó (qua checkpointer). Streamlit truyền
    vào session id riêng cho mỗi người dùng.
    Có failover key: nếu gặp lỗi quota, chuyển key và rebuild graph, thử
    lại toàn bộ request 1 lần cho mỗi key còn lại.
    """
    logger.info("Agent nhận câu hỏi (thread_id=%s): %r", thread_id, question)

    manager = get_key_manager()
    config = {"configurable": {"thread_id": thread_id}}
    last_error: Exception | None = None

    for attempt in range(manager.num_keys):
        try:
            graph = _get_graph()
            result = graph.invoke({"messages": [{"role": "user", "content": question}]}, config=config)
            answer = result["messages"][-1].content
            logger.info("Agent trả lời: %r", str(answer)[:200])
            return answer
        except Exception as e:
            last_error = e
            if is_quota_error(e) and attempt < manager.num_keys - 1:
                manager.mark_exhausted()
                continue
            raise
    raise last_error
