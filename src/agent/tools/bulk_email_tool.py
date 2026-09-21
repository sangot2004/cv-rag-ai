from langchain_core.tools import tool

from src.notification.bulk_email_drafter import draft_bulk_emails


@tool
def draft_bulk_interview_invitations(
    candidate_ids: list[str], position: str, interview_details: str = ""
) -> str:
    """Soạn NỘI DUNG (chưa gửi) email mời phỏng vấn cho NHIỀU ứng viên cùng
    lúc. Dùng khi HR nói "soạn mail cho các ứng viên này/họ/nhóm vừa tìm
    được" — candidate_ids PHẢI lấy từ candidate_id đã xuất hiện trong các
    tin nhắn TRƯỚC ĐÓ của cuộc hội thoại (kết quả filter_candidates_sql,
    semantic_search_cv, find_top_candidates_for_jd...). KHÔNG tự bịa ra
    candidate_id nếu hội thoại trước đó chưa hề nhắc tới — nếu không chắc
    chắn danh sách nào HR đang muốn nói tới, hỏi lại HR để xác nhận trước
    khi gọi tool này.

    QUAN TRỌNG: tool này CHỈ soạn nội dung để hiển thị, KHÔNG hề gửi email
    thật — giống draft_interview_invitation (bản đơn lẻ). Việc gửi thật
    luôn phải qua tab "Gửi thư mời" trên giao diện, không có cách nào gửi
    qua chat.
    """
    if not candidate_ids:
        return "Không có candidate_id nào để soạn - hãy tìm ứng viên trước, hoặc cho biết rõ danh sách."

    results = draft_bulk_emails(candidate_ids, position, interview_details)

    success = [r for r in results if r["error"] is None]
    failed = [r for r in results if r["error"] is not None]

    lines = [f"Đã soạn xong {len(success)}/{len(results)} email (CHƯA GỬI - cần xác nhận):"]
    for r in success:
        lines.append(f"\n--- {r['full_name']} ({r['candidate_id']}) ---")
        lines.append(f"Subject: {r['subject']}")
        lines.append(r["body"][:200] + ("..." if len(r["body"]) > 200 else ""))

    if failed:
        lines.append(f"\n {len(failed)} candidate bị lỗi/không có quyền xem:")
        for r in failed:
            lines.append(f"- {r['candidate_id']}: {r['error']}")

    return "\n".join(lines)
