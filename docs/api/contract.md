# API v0.1 — Auth và text chat

Prefix nghiệp vụ: `/api`. UUID truyền bằng chuỗi; thời gian ISO 8601 UTC.
Login nhận JSON; các endpoint còn lại nhận `Authorization: Bearer <token>`.
Token opaque, được lưu băm trong DB. Role/phòng ban lấy từ session.
Thông số và kiểu response đầy đủ xem `/openapi.json`.

## Endpoints

| Method | Đường dẫn | Thành công |
| --- | --- | --- |
| GET | /health | 200, status ok |
| POST | /api/auth/login | 200, token, expires_in, expires_at, user |
| GET | /api/auth/me | 200, identity |
| POST | /api/auth/logout | 204 |
| POST | /api/conversations | 201, thread_id/title/created_at/updated_at |
| GET | /api/conversations?limit=50 | 200, items và limit |
| GET | /api/conversations/{id}/messages | 200, history và trạng thái |
| DELETE | /api/conversations/{id} | 204 |
| POST | /api/conversations/{id}/messages | 200, kết quả chat |
| POST | /api/conversations/{id}/resume | 200, kết quả chat |
| POST | /api/conversations/{id}/feedback | 201, message_id và feedback |

Danh sách tối đa 50 hội thoại, chưa có pagination đầy đủ. POST tạo hội thoại nhận
`{}` hoặc bỏ body. Input từ chối trường ngoài schema, kể cả role/owner/department.

## Gửi tin và đọc lại

Request: `{"question": "..." }`, từ 1 đến 20.000 ký tự, không chỉ khoảng trắng.

Kết quả:

```json
{
  "type": "answer",
  "thread_id": "...",
  "message": {"id": "...", "role": "assistant", "content": "..."}
}
```

History:

```json
{
  "thread_id": "...",
  "messages": [
    {"id": "...", "role": "user", "content": "..."},
    {"id": "...", "role": "assistant", "content": "..."}
  ],
  "pending_confirmations": [],
  "execution_status": "idle"
}
```

Messages và pending lấy từ cùng một snapshot. Chỉ text người dùng/câu trả lời
cuối được hiển thị; không lộ tool message, tool-call hoặc reasoning block.
ID dùng ID trong checkpoint; dữ liệu cũ thiếu ID dùng hash ổn định theo
thread/index/role/content.

| execution_status | Cách xử lý của FE |
| --- | --- |
| idle | Có thể gửi câu hỏi |
| running | Đang chạy; đọc lại trạng thái sau, không gửi lại POST |
| awaiting_confirmation | Hiển thị các form chờ xác nhận |
| failed | Lượt chạy lỗi đã lưu vào checkpoint; hiện lỗi và cho tạo hội thoại mới |
| interrupted | Có bước chưa hoàn tất sau gián đoạn/restart; cho tạo hội thoại mới |

Trạng thái running nằm trong bộ nhớ. Sau restart, công việc chưa hoàn tất có thể
thành interrupted. Nếu thất bại trước khi ghi checkpoint, history có thể vẫn idle.
Không có cơ chế tự chạy lại graph lỗi trong bản đầu.

## Xác nhận JD

Kết quả `confirmation_required` trả `pending_confirmations` dạng danh sách:

```json
{
  "type": "confirmation_required",
  "thread_id": "...",
  "pending_confirmations": [{
    "confirmation_id": "...",
    "type": "confirm_jd_criteria",
    "criteria": {
      "position_title": "Data Engineer",
      "required_skills": ["Python", "SQL"],
      "min_years_experience": 1,
      "preferred_education": null,
      "top_k": 5
    }
  }]
}
```

POST resume:

```json
{
  "confirmation_id": "...",
  "confirmed": true,
  "edited_criteria": {"top_k": 3, "min_years_experience": null}
}
```

- ID bắt buộc, lấy từ response/history mới nhất.
- Sửa từng phần: trường bỏ qua giữ nguyên, null chỉ hợp lệ cho years/education.
- top_k là integer 1–10, years không âm, kỹ năng là danh sách chuỗi không rỗng.
- Hủy bằng confirmed=false; edited_criteria có thể bỏ qua.
- Một lượt có thể có nhiều yêu cầu xác nhận; resume xử lý đúng ID đã chọn.
- Extraction được lưu bằng LangGraph task trước interrupt, resume dùng lại dữ liệu đó.
- Kết quả resume có thể là answer, confirmation_required hoặc cancelled
  (cancelled có message=null nếu không sinh câu trả lời).

## Feedback và xóa

Feedback: `{"message_id": "...", "feedback": "up"}` (hoặc down).
Backend tìm câu hỏi/câu trả lời trong hội thoại thuộc người dùng; không nhận text
câu trả lời từ client. Chính sách append: gửi hai lần sẽ lưu hai feedback.

DELETE đặt dấu xóa trong MySQL, xóa feedback, rồi dọn checkpoint SQLite.
Nếu bước cuối lỗi, trả 503 CONVERSATION_CLEANUP_PENDING. Hội thoại đã bị ẩn và
không thể đọc/chat lại. Chính chủ có thể gọi DELETE lại để dọn tiếp; thành công 204.

## Lỗi

```json
{
  "error": {
    "code": "CONVERSATION_NOT_FOUND",
    "message": "Không tìm thấy hội thoại hoặc bạn không có quyền truy cập.",
    "request_id": "..."
  }
}
```

Response có header X-Request-ID. ID do server sinh, dùng tra log, **không phải
idempotency key**. Lỗi không trả input mật khẩu, raw exception hay thông tin provider.

| HTTP | code chính |
| --- | --- |
| 401 | AUTHENTICATION_REQUIRED |
| 403 | FORBIDDEN |
| 404 | CONVERSATION_NOT_FOUND, MESSAGE_NOT_FOUND |
| 409 | CONVERSATION_BUSY, CONFIRMATION_PENDING, NO_PENDING_CONFIRMATION, STALE_CONFIRMATION, EXECUTION_INCOMPLETE |
| 422 | VALIDATION_ERROR |
| 503 | DEPENDENCY_UNAVAILABLE, CONVERSATION_CLEANUP_PENDING |
| 504 | DEPENDENCY_TIMEOUT |
| 500 | INTERNAL_ERROR |

## Giới hạn vận hành

- Khóa ask/resume/delete/feedback theo hội thoại, trong **một tiến trình**.
- Request đồng thời cùng hội thoại trả 409. Hội thoại khác có thể chạy song song.
- Chưa có durable idempotency: POST lặp lại sau khi lượt trước kết thúc có thể
  thực thi thêm một lượt. FE cần khóa nút gửi và xử lý mất kết nối bằng GET history.
- Chat đồng bộ trong worker thread. Client timeout/disconnect không hủy graph;
  khóa chỉ nhả khi callable kết thúc. Không có deadline cho toàn bộ lượt chat.
  504 biểu diễn exception timeout từ dịch vụ phụ thuộc.
- Chưa có queue chat, streaming, upload, API quản trị, distributed locks, rate limit
  theo client, refresh token/cookie hoặc readiness.
- CORS không thay thế xác thực.
