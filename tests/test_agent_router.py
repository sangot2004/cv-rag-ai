"""
Test xem Agent có chọn đúng tool mới (đã bổ sung) hay không.

Yêu cầu trước khi chạy:
- Đã đăng ký các tool mới trong src/agent/router.py (ví dụ:
  get_candidate_certificates, count_candidates_by_criteria,
  get_recent_candidates...)

Cách chạy:
    PYTHONPATH=. python evals/test_agent_router.py
"""

from src.agent.router import ask
import sys

sys.path.insert(0, ".")


TEST_CASES = [
    ("Ứng viên nào có chứng chỉ AWS?", "get_candidate_certificates"),
    ("Có bao nhiêu ứng viên trong hệ thống?", "count_candidates_by_criteria"),
    ("5 CV mới nộp gần đây nhất là gì?", "get_recent_candidates"),
]


def extract_text(answer) -> str:
    """Lấy phần text từ output của ask(), bỏ qua block extras/signature."""
    if isinstance(answer, list):
        parts = []
        for block in answer:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
        return "\n".join(parts) if parts else str(answer)
    return str(answer)


def extract_tool_calls(answer) -> list[str]:
    """
    Lấy danh sách tên tool đã được Agent gọi, nếu có xuất hiện trong output.
    LƯU Ý: cấu trúc block tool-call phụ thuộc vào cách router.py trả về.
    Nếu ask() hiện tại KHÔNG trả kèm thông tin tool_use, hàm này sẽ trả về
    list rỗng — cần sửa router.py để expose thêm thông tin đó (xem ghi chú
    cuối file).
    """
    tools = []
    if isinstance(answer, list):
        for block in answer:
            if isinstance(block, dict):
                block_type = block.get("type", "")
                if block_type in ("tool_use", "tool_call"):
                    name = block.get("name") or block.get("tool_name")
                    if name:
                        tools.append(name)
    return tools


def main():
    print("=" * 60)
    print("TEST: Agent có chọn đúng tool mới không")
    print("=" * 60)

    results = []

    for question, expected_tool in TEST_CASES:
        print(f"\nCâu hỏi: {question}")
        print(f"Kỳ vọng tool: {expected_tool}")

        answer = ask(question)

        called_tools = extract_tool_calls(answer)
        text = extract_text(answer)

        print(f"Tool thực sự được gọi: {called_tools or '(không phát hiện được — xem ghi chú)'}")
        print(f"Câu trả lời:\n{text}")

        is_match = expected_tool in called_tools if called_tools else None
        results.append((question, expected_tool, called_tools, is_match))

        print("-" * 60)

    # Tổng kết
    print("\n" + "=" * 60)
    print("TỔNG KẾT")
    print("=" * 60)
    for question, expected_tool, called_tools, is_match in results:
        if is_match is None:
            status = "?  (không xác định được tool đã gọi)"
        elif is_match:
            status = "✅ đúng"
        else:
            status = "❌ sai"
        print(f"[{status}] {question}")
        print(f"     kỳ vọng: {expected_tool} | thực tế: {called_tools}")

    print(
        "\nGhi chú: nếu mọi dòng đều hiện '(không xác định được tool đã gọi)',\n"
        "nghĩa là hàm ask() trong router.py hiện chỉ trả về text, không trả\n"
        "kèm thông tin tool_use. Cần sửa router.py để trả thêm tool call\n"
        "(ví dụ trả về dict {'answer': ..., 'tool_calls': [...]}) hoặc bật\n"
        "log/print tên tool ngay trong lúc agent chạy (verbose=True nếu dùng\n"
        "LangChain AgentExecutor) để đối chiếu bằng mắt."
    )


if __name__ == "__main__":
    main()
