from src.agent.router import _get_graph
from evals.evaluators import AGENT_EVALUATORS
from langsmith import evaluate
import sys

sys.path.insert(0, ".")

DATASET_NAME = "cv-agent-tool-selection-eval"


def target(inputs: dict) -> dict:
    """Chạy Agent, lấy ra tên tool ĐẦU TIÊN mà Agent gọi (đủ để đánh giá
    routing đúng hay sai). Dùng chung _get_graph() với router.py để có key failover
    tự động; mỗi câu hỏi dùng 1 thread_id riêng để không lẫn lịch sử giữa
    các example trong dataset.
    """
    graph = _get_graph()
    config = {"configurable": {"thread_id": f"eval-{hash(inputs['question'])}"}}
    result = graph.invoke(
        {"messages": [{"role": "user", "content": inputs["question"]}]}, config=config
    )

    tool_called = None
    for msg in result["messages"]:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            tool_called = tool_calls[0]["name"]
            break

    return {"tool_called": tool_called}


def main():
    results = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=AGENT_EVALUATORS,
        experiment_prefix="agent-tool-selection-eval",
        description="Đánh giá Agent có chọn đúng tool theo câu hỏi không",
    )
    print("\nHoàn thành. Xem chi tiết kết quả trên LangSmith dashboard.")
    print(results)


if __name__ == "__main__":
    main()
