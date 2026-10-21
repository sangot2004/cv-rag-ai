# Chạy API local

## 1. Môi trường

Dùng Python 3.12, đứng ở thư mục gốc dự án:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Giữ file `.env` hiện có. API dùng chung tài khoản, MySQL, các phiên bản prompt
LangSmith và cấu hình dịch vụ với Streamlit. Không chép đè `.env` bằng file mẫu.

Nếu database chưa cập nhật migration auth/ownership:

```bash
alembic current
alembic upgrade head
```

Bản API này không thêm migration. Đăng nhập cần MySQL; chat cần thêm các dịch vụ
của tool được gọi và Gemini/LangSmith. `/health` chỉ kiểm tra tiến trình, không
kiểm tra readiness của các dịch vụ đó.

Cấu hình bổ sung trong `.env`:

```dotenv
API_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CHAT_HISTORY_PATH=chat_history.db
```

Đường dẫn checkpoint tương đối luôn tính từ thư mục gốc repository, kể cả khi
khởi động từ working directory khác. Có thể đặt đường dẫn tuyệt đối.
CORS chỉ cho phép các origin khai báo; không dùng wildcard.

## 2. Chạy server

Dừng Streamlit trước khi thử API với cùng dữ liệu chat.

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
```

- Swagger: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json
- Liveness: http://127.0.0.1:8000/health

Bản đầu dùng khóa trong bộ nhớ: **một tiến trình ghi chat**. Không chạy nhiều
Uvicorn workers hoặc chạy API/Streamlit cùng ghi vào checkpoint đó.
Streamlit vẫn chạy riêng bằng `streamlit run app.py`.
Nếu dùng `--reload` trong lúc phát triển, chờ chat hoàn tất trước khi sửa code.

## 3. Thử bằng Swagger

1. Mở `POST /api/auth/login`, chọn **Try it out** và nhập username/password của
   tài khoản đã tạo bằng `scripts/manage_users.py`.
2. Copy `access_token` trong response. Bấm **Authorize**, nhập token
   (Swagger tự thêm tiền tố Bearer).
3. Gọi `GET /api/auth/me` để xác nhận tài khoản.
4. Gọi `POST /api/conversations` với body `{}`. Copy `thread_id`.
5. Gọi `POST /api/conversations/{thread_id}/messages`:

```json
{ "question": "Ứng viên nào biết Python?" }
```

6. Đọc lại bằng `GET /api/conversations/{thread_id}/messages`.
   ID câu trả lời phải giống ID trong kết quả bước 5.
7. Thử câu hỏi có JD. Khi nhận `confirmation_required`, lấy một
   `confirmation_id` trong `pending_confirmations` và gọi `/resume`:

```json
{
  "confirmation_id": "COPY_ID_FROM_RESPONSE",
  "confirmed": true,
  "edited_criteria": { "top_k": 3 }
}
```

Hủy bằng `confirmed: false`. Nếu còn xác nhận khác, tiếp tục với ID còn lại. 8. Gửi `/feedback` với `{"message_id": "ID_CAU_TRA_LOI", "feedback": "up"}`. 9. Đăng nhập tài khoản khác và thử đọc hội thoại này: phải nhận `404`.
Hai tester cùng phòng ban cũng có lịch sử riêng. 10. Xóa hội thoại bằng DELETE, rồi logout. Hai thao tác thành công trả `204`.

## 4. Chạy test offline

API ứng viên mới nằm trong nhóm **candidates**, gồm GET danh sách và GET chi tiết,
chỉ dành cho admin. Xem [cách test và bộ lọc](candidates.md). Restart API để nạp routes mới.

```bash
LANGCHAIN_TRACING_V2=false LANGSMITH_TRACING=false OPS_ENABLED=false \
  python -m pytest tests/api tests/test_double_opt_in.py -q

LANGCHAIN_TRACING_V2=false LANGSMITH_TRACING=false OPS_ENABLED=false \
  python -m pytest -q
```

Test API dùng metadata SQLite và checkpoint SQLite trong thư mục tạm, model giả
và LangGraph thật. Không gọi Gemini, gửi email, hoặc sửa dữ liệu MySQL đang dùng.
Test này kiểm chứng HTTP, ownership, ContextVar xuyên qua tool, interrupt/replay,
feedback và cạnh tranh trong một tiến trình. Vẫn cần thử thủ công với MySQL và
các provider thật để kiểm chứng cấu hình triển khai.

Môi trường kiểm chứng: Python 3.12; FastAPI 0.143.2; Uvicorn 0.52.4;
Starlette 1.6.0; LangGraph 1.2.11; LangChain 1.3.15; SQLite checkpointer 3.1.1;
Pydantic 2.13.4; httpx 0.28.1.

Nhóm **interviews** cho admin: xem [API câu hỏi phỏng vấn](interviews.md). Cần restart FastAPI sau cập nhật; dùng một worker như cấu hình hiện tại.

Module email cần migration `0013` và Celery worker để gửi. Hướng dẫn: [emails.md](emails.md). Nháp không tự gửi.

Quản trị phòng ban/vị trí/tài khoản, gán CV, upload và theo dõi tác vụ cần migration
`0014`. Upload cần MinIO/Redis; xử lý dùng worker/pipeline hiện có. Xem
[administration-ingestion.md](administration-ingestion.md) để chạy và kiểm chứng từng bước.
