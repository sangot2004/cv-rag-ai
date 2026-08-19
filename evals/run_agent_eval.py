"""
Chạy eval cho Agent — kiểm tra có gọi đúng tool theo từng câu hỏi mẫu không.

Cách chạy:
    python evals/run_agent_eval.py
"""

from src.agent.agent_executor import build_agent_executor
from evals.evaluators import AGENT_EVALUATORS
from langsmith import evaluate
import sys

sys.path.insert(0, ".")


DATASET_NAME = "cv-agent-tool-selection-eval"

_graph = build_agent_executor()


def target(inputs: dict) -> dict:
    """Chạy Agent, lấy ra tên tool ĐẦU TIÊN mà Agent gọi (đủ để đánh giá
    routing đúng hay sai — không cần quan tâm câu trả lời cuối cùng ở eval
    này, vì mục tiêu chỉ là kiểm tra tool selection, không phải chất lượng
    câu trả lời).
    """
    result = _graph.invoke({"messages": [{"role": "user", "content": inputs["question"]}]})

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
