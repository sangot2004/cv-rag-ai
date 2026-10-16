# Bản triển khai API đầu tiên

Triển khai phần auth, hội thoại, text chat, xác nhận JD và feedback theo kế hoạch API.
Chi tiết vận hành ở [setup](setup.md), JSON/mã lỗi ở [contract](contract.md).

## Cấu trúc

- `main.py`: entrypoint Uvicorn.
- `src/api/app.py`: app factory, CORS, lifespan.
- `src/api/dependencies.py`: đọc bearer credential.
- `src/api/middleware.py`, `exception_handlers.py`: request ID, lỗi an toàn.
- `src/api/routes/`: health, auth, conversations, chat.
- `src/api/schemas/`: hợp đồng HTTP.
- `src/auth/errors.py`: phân biệt 401/403/404, giữ lớp cha AccessDenied.
- `src/chat/service.py`: điều phối shared cho API và router Streamlit.
- `src/chat/concurrency.py`: khóa thao tác cùng hội thoại.
- `src/chat/message_adapter.py`: text/ID/pending projection.
- `src/chat/criteria.py`: kiểm tra tiêu chí sửa.
- `src/chat/checkpoints.py`: lifecycle SQLite, đường dẫn thống nhất, đọc state.
- `src/agent/router.py`: invoke trong auth/department scope.
- `src/agent/tools/jd_matching_tool.py`: lưu extraction bằng task trước interrupt.
- `tests/api/`: HTTP integration với DB tạm và model giả.

## Các quyết định so với bản đề xuất

1. Dùng `pending_confirmations[]` và `confirmation_id` bắt buộc ở API vì graph
   có thể ngắt tại nhiều tool trong cùng lượt.
2. Resume dùng mapping ID → giá trị; task đã hoàn tất không được trả lại như pending.
3. Khóa cả feedback để phối hợp với DELETE; DELETE được retry trên tombstone đúng chủ.
4. History không cần khởi tạo Gemini hoặc tải prompt.
5. Không tự lặp graph.invoke khi hết quota: input/tool có thể đã được checkpoint.
   Key manager xoay key cho lần chạy tiếp theo.
6. Giữ auth_scope và toàn bộ nghiệp vụ trong cùng sync route.
7. Tiếp tục dùng schema DB hiện tại; chưa cần migration cho API.
8. Docker runtime đổi sang Python 3.12 để khớp môi trường đã test.

## Các bước tiếp theo

Sau khi test thủ công qua Swagger với provider thật, xây FE theo contract.
Rate limit, distributed coordination, idempotency/job chat, cookie/BFF và các API
admin sẽ cần thiết kế riêng trước khi triển khai cho nhiều người dùng bên ngoài.
