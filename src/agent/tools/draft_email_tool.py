from langchain_core.tools import tool

from src.notification.email_drafter import draft_interview_email


@tool
def draft_interview_invitation(candidate_id: str, position: str, interview_details: str = "") -> str:
    """Soạn NỘI DUNG (chưa gửi) email mời phỏng vấn cho 1 ứng viên cụ thể.
    Dùng khi HR yêu cầu "soạn mail mời phỏng vấn", "viết thư mời PV cho
    ứng viên này". interview_details là thông tin HR đã cung cấp trong câu
    hỏi (thời gian, địa điểm, hình thức) — nếu HR không cho biết thì để
    rỗng, KHÔNG tự bịa.

    QUAN TRỌNG: tool này CHỈ soạn nội dung để hiển thị cho HR xem, KHÔNG
    hề gửi email thật. Việc gửi thật phải làm ở màn hình riêng (tab "Gửi
    thư mời" trên giao diện), sau khi HR tự xác nhận — không có cách nào
    qua chat để gửi email thật, kể cả khi HR yêu cầu trực tiếp trong câu
    hỏi. Nếu HR hỏi "gửi luôn giúp tôi", hãy giải thích rằng cần qua tab
    riêng để xác nhận trước khi gửi, không tự ý coi đó là đã gửi.
    """
    draft = draft_interview_email(candidate_id, position, interview_details)
    if draft is None:
        return f"Không tìm thấy candidate_id={candidate_id} hoặc bạn không có quyền xem ứng viên như này."

    return (
        f"Đã soạn xong (CHƯA GỬI - cần xác nhận ở tab 'Gửi thư mời'):\n\n"
        f"subject: {draft.subject}\n\n"
        f"{draft.body}"
    )
