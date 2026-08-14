import logging

from src.agent.agent_executor import build_agent_executor

logger = logging.getLogger(__name__)

_graph = None


def _get_graph():
    """Lazy build — tránh khởi tạo LLM client lúc import module."""
    global _graph
    if _graph is None:
        _graph = build_agent_executor()
    return _graph


def ask(question: str) -> str:
    """Entrypoint duy nhất cho Luồng C — nhận câu hỏi tiếng Việt tự nhiên,
    Agent tự quyết định gọi tool nào (SQL filter / semantic search /
    evaluation) qua tool-calling của Gemini, không cần router thủ công
    tách riêng — bản thân agent graph đã đóng vai trò router.

    LangChain 1.x: invoke bằng {"messages": [...]}, lấy nội dung câu trả
    lời cuối cùng từ result["messages"][-1].content (khác hẳn API cũ
    result["output"] của AgentExecutor).
    """
    logger.info("Agent nhận câu hỏi: %r", question)

    result = _get_graph().invoke({"messages": [{"role": "user", "content": question}]})
    answer = result["messages"][-1].content

    logger.info("Agent trả lời: %r", str(answer)[:200])
    return answer
