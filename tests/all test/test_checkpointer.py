"""
Test riêng lịch sử hội thoại (checkpointer) của Agent.

Mục đích: kiểm tra Agent có nhớ được ngữ cảnh giữa các lượt hỏi trong CÙNG
1 thread_id hay không, và có bị "rò rỉ" ngữ cảnh sang thread_id KHÁC hay không.

Yêu cầu trước khi chạy: đã có ít nhất vài candidate trong hệ thống
(đã chạy test_pipeline.py / ingest CV trước đó).

Cách chạy:
    PYTHONPATH=. python evals/test_checkpointer.py
"""

from src.agent.router import ask
import sys
import uuid

sys.path.insert(0, ".")


def step(title: str):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def extract_text(answer):
    """Chuẩn hóa output của ask() về string, phòng trường hợp trả về
    list block kiểu [{'type': 'text', 'text': ...}, ...]."""
    if isinstance(answer, list):
        parts = [
            b["text"] for b in answer
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        return "\n".join(parts) if parts else str(answer)
    return str(answer)


def ask_and_print(question: str, thread_id: str, label: str = "") -> str:
    print(f"\n[thread={thread_id}] {label}")
    print(f"Câu hỏi: {question}")
    raw = ask(question, thread_id=thread_id)
    text = extract_text(raw)
    print(f"Trả lời:\n{text}")
    return text


def test_1_same_thread_remembers_context():
    """Test chính theo yêu cầu: cùng thread_id -> câu hỏi 2 phải hiểu được
    'danh sách đó' là danh sách đã trả lời ở câu 1, không hỏi lại."""
    step("Test 1: Cùng thread_id — Agent phải nhớ ngữ cảnh")

    thread_id = f"test-thread-{uuid.uuid4().hex[:8]}"

    ask_and_print(
        "Liệt kê 3 ứng viên gần đây nhất",
        thread_id=thread_id,
        label="Lượt 1 — thiết lập ngữ cảnh",
    )

    answer_2 = ask_and_print(
        "So sánh 2 người đầu tiên trong danh sách đó",
        thread_id=thread_id,
        label="Lượt 2 — dựa vào ngữ cảnh lượt 1",
    )

    # Heuristic kiểm tra nhanh: nếu Agent "quên" ngữ cảnh, nó thường sẽ
    # hỏi lại kiểu "bạn muốn nói đến danh sách nào?" / "vui lòng cung cấp..."
    confusion_markers = [
        "danh sách nào",
        "vui lòng cung cấp",
        "bạn có thể cho tôi biết",
        "không rõ bạn đang nhắc",
        "which list",
        "please provide",
    ]
    lowered = answer_2.lower()
    is_confused = any(marker in lowered for marker in confusion_markers)

    print("\n--- Kết quả Test 1 ---")
    if is_confused:
        print("[FAIL] Agent có vẻ đã hỏi lại / không nhớ ngữ cảnh lượt 1.")
    else:
        print("[PASS - cần tự soát lại bằng mắt] Agent không hỏi lại ngay lập tức, "
              "nhưng bạn vẫn nên đọc kỹ câu trả lời để chắc chắn nó so sánh "
              "ĐÚNG 2 người trong danh sách lượt 1 (không tự bịa 2 người khác).")

    return thread_id, answer_2


def test_2_different_thread_does_not_leak_context(thread_1_id: str = None, thread_1_answer: str = None):
    """Test phụ: thread_id KHÁC nhau phải KHÔNG chia sẻ ngữ cảnh.
    Nếu hỏi 'so sánh 2 người đầu tiên' ở 1 thread_id hoàn toàn mới (chưa từng
    hỏi câu liệt kê nào trước đó), Agent phải hỏi lại / báo thiếu ngữ cảnh,
    KHÔNG được tự nhớ nhầm sang dữ liệu của thread khác.

    Nếu truyền vào thread_1_id/thread_1_answer (kết quả Test 1), hàm sẽ tự
    động dò xem answer của Test 2 có nhắc lại đúng candidate_id nào đã xuất
    hiện ở Test 1 hay không — đây là bằng chứng RÕ RÀNG NHẤT cho việc rò rỉ
    state giữa các thread (đối lập với việc Agent chỉ tự gọi lại tool để lấy
    danh sách MỚI, hoàn toàn hợp lệ)."""
    step("Test 2: Thread_id khác nhau — không được rò rỉ ngữ cảnh")

    thread_id_new = f"test-thread-{uuid.uuid4().hex[:8]}"

    answer = ask_and_print(
        "So sánh 2 người đầu tiên trong danh sách đó",
        thread_id=thread_id_new,
        label="Thread hoàn toàn mới, CHƯA từng hỏi câu liệt kê nào",
    )

    confusion_markers = [
        "danh sách nào",
        "vui lòng cung cấp",
        "bạn có thể cho tôi biết",
        "không rõ bạn đang nhắc",
        "which list",
        "please provide",
    ]
    lowered = answer.lower()
    is_confused = any(marker in lowered for marker in confusion_markers)

    print("\n--- Kết quả Test 2 ---")
    if is_confused:
        print("[PASS] Agent đúng đắn báo thiếu ngữ cảnh ở thread mới, "
              "không bị rò rỉ dữ liệu từ thread khác.")
        return

    # Chưa hỏi lại -> cần phân biệt "tự gọi tool mới" (OK) vs "rò rỉ state" (BUG)
    if thread_1_answer:
        import re
        # Tìm các candidate_id dạng UUID trong cả 2 câu trả lời để so khớp
        uuid_pattern = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
        ids_thread_1 = set(re.findall(uuid_pattern, thread_1_answer))
        ids_thread_2 = set(re.findall(uuid_pattern, answer))
        overlap = ids_thread_1 & ids_thread_2

        print(
            f"\nCandidate_id xuất hiện ở Test 1 (thread={thread_1_id}): {ids_thread_1 or '(không tìm thấy UUID nào trong text)'}")
        print(
            f"Candidate_id xuất hiện ở Test 2 (thread={thread_id_new}): {ids_thread_2 or '(không tìm thấy UUID nào trong text)'}")

        if overlap:
            print(f"\n[FAIL - RÒ RỈ STATE] Phát hiện {len(overlap)} candidate_id "
                  f"TRÙNG giữa 2 thread khác nhau: {overlap}")
            print("Đây là bằng chứng checkpointer đang chia sẻ nhầm state giữa "
                  "các thread_id khác nhau — CẦN SỬA GẤP trước khi lên production.")
        elif ids_thread_1 and ids_thread_2:
            print("\n[PASS] Không có candidate_id nào trùng giữa 2 thread — "
                  "Agent ở Test 2 đã tự gọi lại tool để lấy danh sách MỚI, "
                  "không dùng nhầm dữ liệu của Test 1. Đây là hành vi hợp lệ.")
        else:
            print("\n[KHÔNG KẾT LUẬN ĐƯỢC BẰNG UUID] Câu trả lời không chứa "
                  "candidate_id dạng UUID rõ ràng (có thể Agent chỉ trả lời "
                  "bằng tên). Hãy tự đọc và so sánh TÊN ứng viên giữa Test 1 "
                  "và Test 2 bằng mắt để kết luận.")
    else:
        print("[CẦN KIỂM TRA THỦ CÔNG] Không có dữ liệu Test 1 để đối chiếu — "
              "hãy tự đọc câu trả lời Test 1 và Test 2, so sánh xem có nhắc "
              "cùng đúng những ứng viên nào không.")


def test_3_multi_turn_conversation():
    """Test mở rộng: hội thoại nhiều lượt liên tiếp trong cùng 1 thread,
    kiểm tra Agent có duy trì ngữ cảnh xuyên suốt không chỉ 2 lượt mà
    nhiều lượt hơn."""
    step("Test 3: Hội thoại nhiều lượt (multi-turn) trong cùng thread")

    thread_id = f"test-thread-{uuid.uuid4().hex[:8]}"

    turns = [
        "Liệt kê 3 ứng viên gần đây nhất",
        "Trong 3 người đó, ai có nhiều kinh nghiệm nhất?",
        "Người đó biết những kỹ năng gì?",
        "So sánh người đó với ứng viên thứ 2 trong danh sách ban đầu",
    ]

    for i, question in enumerate(turns, start=1):
        ask_and_print(question, thread_id=thread_id, label=f"Lượt {i}")

    print("\n--- Kết quả Test 3 ---")
    print("Tự đọc lại 4 câu trả lời ở trên: Agent có giữ được mạch hội thoại "
          "xuyên suốt 4 lượt không, hay bắt đầu 'quên' từ lượt 3-4 trở đi? "
          "(checkpointer có thể giới hạn window lịch sử, đáng kiểm tra nếu "
          "hội thoại dài mà Agent bắt đầu trả lời sai/lặp lại câu hỏi cũ).")


def main():
    step("TEST CHECKPOINTER / LỊCH SỬ HỘI THOẠI")
    print("Yêu cầu: đã có candidate trong hệ thống (chạy test_pipeline.py trước).")
    input("\n-> Enter để bắt đầu Test 1...")

    thread_1_id, thread_1_answer = test_1_same_thread_remembers_context()
    input("\n-> Enter để tiếp tục Test 2...")

    test_2_different_thread_does_not_leak_context(thread_1_id, thread_1_answer)
    input("\n-> Enter để tiếp tục Test 3 (multi-turn)...")

    test_3_multi_turn_conversation()

    step("HOÀN THÀNH — Test checkpointer")
    print("Lưu ý: các nhãn [PASS]/[FAIL] ở trên chỉ là heuristic kiểm tra "
          "nhanh bằng từ khóa. Luôn tự đọc lại nội dung câu trả lời để "
          "xác nhận Agent thực sự hiểu đúng ngữ cảnh, không chỉ 'không hỏi lại'.")


if __name__ == "__main__":
    main()
