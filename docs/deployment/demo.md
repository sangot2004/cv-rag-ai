# Chạy bản demo CV RAG AI

Bộ demo gồm Next.js/BFF, FastAPI, Celery worker, MySQL, Redis, Qdrant, MinIO
và Caddy HTTPS trong một file `docker-compose.yml`. Mặc định chỉ chạy các dịch vụ
dữ liệu; profile `demo` bật API/worker/frontend/HTTPS, profile `scheduler` bật Beat.
Tên container và các volume dữ liệu cũ được giữ để tiếp tục dùng môi trường hiện có.

## 1. Chuẩn bị môi trường

Cần Docker Engine/Desktop và Docker Compose v2. Máy cần đủ RAM/disk cho MySQL,
Qdrant và model rerank CPU; image API có PyTorch CPU. Lần build đầu tải dependencies;
lần tìm kiếm đầu tiên có thể tải model Hugging Face vào volume `model_cache`.

Tại thư mục gốc repository:

```bash
mkdir -p deploy/demo/runtime
openssl rand -hex 24
```

Dùng `.env` đang có; bổ sung biến mới theo `.env.example`. Nếu cài lần đầu, tạo
`.env` từ `.env.example`, đặt các mật khẩu database/storage ngẫu nhiên khác nhau.
Với database đã có, giữ thông tin đăng nhập đã tạo. Password database mới dùng
chữ/số hexadecimal để không cần URL-encode trong DSN. Điền `GOOGLE_API_KEY`
và `LANGSMITH_API_KEY` có quyền đọc
các prompt đã pin trong `src/llm/prompt_store.py`. Tắt tracing không tắt việc đọc prompt.
Chọn các model thực sự được API key của bạn hỗ trợ.

`OPS_MODEL_PRICES_JSON={}` hiển thị chi phí chưa biết. Nếu dùng free tier, cấu hình
giá 0 cho đúng model theo [Ops setup](../../OPS_SETUP.md); không coi giá chưa biết là 0.

Chọn `DEMO_DOMAIN`:

- Chạy tại máy: `localhost`, mở `https://localhost`.
- Chia sẻ demo: hostname DNS thật, ví dụ `cv.example.com`, trỏ về server.
  Server cần nhận kết nối cổng 80/443 để Caddy cấp certificate.

`APP_ORIGIN` và CORS được tạo từ hostname này. Không thêm scheme, port hoặc slash
vào `DEMO_DOMAIN`. Nếu đổi origin public qua proxy khác, phải sửa `APP_ORIGIN`
đúng origin browser đang dùng.

`.env`, Gmail credentials/token và `deploy/demo/runtime/` được Git ignore,
không nằm trong Docker build context. Frontend chỉ nhận URL API nội bộ, không nhận
khóa Gemini, LangSmith hoặc Gmail.

## 2. Build và khởi động

Chỉ chạy các dịch vụ dữ liệu để dùng cùng API/Next trên máy:

```bash
docker compose up -d
```

Chạy toàn bộ ứng dụng bằng Docker. Nếu đang có lịch sử từ API/Streamlit local,
thực hiện mục **Chuyển lịch sử chat** bên dưới trước lần `up` demo đầu tiên.

```bash
docker compose --profile demo config --quiet
docker compose --profile demo up -d --build
docker compose --profile demo ps -a
docker compose --profile demo logs --tail=60 prepare api worker frontend proxy
```

`prepare` phải kết thúc với exit code 0: chạy `alembic upgrade head`, chuẩn bị bucket
và collection. API/frontend phải healthy. Worker phải có thông báo ready. Nếu
`prepare` thất bại, xem log và sửa trước khi khởi động tiếp.

API chạy **một worker** để bảo đảm khóa hội thoại trong process và SQLite checkpoint.
Không scale API hoặc chạy Streamlit cùng ghi vào checkpoint này. Worker Celery
dùng pool solo; lưu cache model và checkpoint qua các lần restart.

Caddy công bố cổng 80/443. Các cổng dữ liệu giữ nguyên số cổng cũ và mặc định chỉ
bind `127.0.0.1` để API/FE chạy trực tiếp trên máy vẫn truy cập được. API và frontend
container chỉ dùng mạng nội bộ; `DATA_BIND_ADDRESS` điều chỉnh địa chỉ bind khi cần.
Browser truy cập `/api/session/*` và `/api/backend/*` của Next.
API health là liveness; không thay thế kiểm tra database/worker bên dưới.

### Chuyển lịch sử chat từ chạy local sang Docker

MySQL/Qdrant/MinIO tiếp tục dùng volume cũ của cùng Compose project. Checkpoint
SQLite của API trong Docker nằm trong volume `chat_data`; file local
`chat_history.db` không tự chuyển vào volume này. Trước lần chuyển đầu tiên, dừng
API/Streamlit local và tạo bản sao nhất quán của checkpoint:

```bash
sqlite3 chat_history.db ".backup '/tmp/cv-rag-checkpoint-backup.db'"
docker compose --profile demo build api
docker compose --profile demo run --rm --no-deps \
  -v /tmp/cv-rag-checkpoint-backup.db:/import/chat_history.db:ro api python -c \
  'import sqlite3; from pathlib import Path; p=Path("/app/data/chat_history.db"); assert not p.exists(), "Checkpoint Docker da co, can kiem tra truoc khi thay the"; src=sqlite3.connect("file:/import/chat_history.db?mode=ro",uri=True); dst=sqlite3.connect(str(p)); src.backup(dst); dst.close(); src.close()'
```

Chỉ thực hiện khi Docker API chưa chạy và volume checkpoint chưa có dữ liệu.
Nếu `CHAT_HISTORY_PATH` local dùng đường dẫn khác, thay tên file ở lệnh backup.
Sau đó chạy `docker compose --profile demo up -d --build`. Không chạy song song
API local và API Docker dùng chung metadata MySQL với hai checkpoint khác nhau.

## 3. HTTPS tại localhost

Caddy dùng CA cục bộ cho localhost. Xuất chứng chỉ CA:

```bash
docker compose --profile demo exec -T proxy \
  cat /data/caddy/pki/authorities/local/root.crt > /tmp/cv-rag-demo-root.crt
curl --cacert /tmp/cv-rag-demo-root.crt https://localhost/login
```

Để browser tin cậy, nhập certificate này vào trust store trên máy (macOS: Keychain
Access, chọn certificate và đặt tin cậy cho SSL), rồi mở lại browser. Chỉ thực hiện
với certificate của stack mình vừa tạo. Với domain có certificate công khai hợp lệ,
không cần bước nhập CA.

Production dùng cookie `__Host-cv_session`, Secure và HttpOnly. Demo phải đi qua
HTTPS, kể cả khi Next/API ở phía trong dùng HTTP.

## 4. Tạo admin và tester

```bash
docker compose --profile demo exec api \
  python -m scripts.manage_users create demo_admin --role admin
```

Nhập mật khẩu 12–256 ký tự hai lần. Không đặt mật khẩu trong source hoặc command
argument. Lệnh create không ghi đè tài khoản có sẵn.

Đăng nhập admin tại `/login`, sau đó:

1. Tạo Engineering và Sales trong **Phòng ban**.
2. Tạo một vị trí tuyển dụng cho mỗi phòng ban.
3. Trong **Quản lý tài khoản**, tạo `tester_engineering` thuộc Engineering và
   `tester_sales` thuộc Sales, mỗi người có mật khẩu riêng.
4. Upload một CV demo vào từng vị trí. Dùng dữ liệu giả và email thử nghiệm mà bạn
   quản lý nếu muốn kiểm thử gửi thư thật.

Phòng ban mới chưa có CV sẽ hiện danh sách trống. Tester không thấy CV chưa gắn vị trí.
Không có tài khoản hoặc mật khẩu demo cố định được cài sẵn.

## 5. Gmail và scheduler — khi cần demo email

Chuẩn bị OAuth trên máy có browser theo [hướng dẫn email](../api/emails.md), rồi đặt
`credentials.json` và `token.json` vào `deploy/demo/runtime/`. Token phải có quyền
`gmail.modify` và `gmail.send`. UID 10001 trong container cần đọc các file và ghi lại
token khi refresh; trên Linux cần cấp quyền thư mục/file tương ứng.

Không chạy luồng đăng nhập OAuth tương tác trong container. Nếu refresh token đã
bị thu hồi, tạo lại trên máy có browser và cập nhật file runtime.

Worker xử lý yêu cầu được duyệt ngay khi dispatch. Để tự phục hồi outbox và nhận CV
Gmail định kỳ, bật scheduler sau khi cấu hình mailbox:

```bash
docker compose --profile demo --profile scheduler up -d beat
```

Chỉ chạy một Beat. Profile này bật poll inbox mỗi 5 phút và drain outbox mỗi 30 giây.
Mặc định Beat không chạy. Các thư vẫn cần được duyệt theo luồng hiện có.

## 6. Kiểm tra trước demo

```bash
docker compose --profile demo exec api \
  python -m scripts.check_demo --worker --api-url http://api:8000 --frontend-url http://frontend:3000
```

Thêm `--email` để kiểm tra file OAuth/scopes. Script chỉ đọc: kiểm tra migration,
Redis, collection/dimension Qdrant, bucket, checkpoint, cấu hình keys, worker và
HTTP endpoints. Key/scopes tồn tại không chứng minh provider cho phép gọi thật.
Worker solo đang bận có thể chưa trả lời ping trong 3 giây; thử lại khi job xong.

Kiểm tra cookie/Origin/quyền/đăng xuất từ máy có Python dependencies:

```bash
PYTHONPATH=. .venv/bin/python scripts/smoke_demo.py https://localhost \
  --username demo_admin --ca-cert /tmp/cv-rag-demo-root.crt
PYTHONPATH=. .venv/bin/python scripts/smoke_demo.py https://localhost \
  --username tester_engineering --ca-cert /tmp/cv-rag-demo-root.crt
```

Script hỏi mật khẩu, không gọi AI và không gửi thư. Với domain có certificate công
khai, bỏ `--ca-cert`. Tiếp tục [checklist nghiệm thu](../testing/release-checklist.md)
để kiểm chứng Gemini, prompt và Gmail với dữ liệu demo được phép sử dụng.

## 7. Cập nhật, lưu dữ liệu và dừng

Sau khi cập nhật source, build/up lại; `prepare` thực hiện migration trước khi API
chạy. Giữ version image/digest đã nghiệm thu khi phát hành; các tag service trong
`.env` có thể pin lại. Requirements Python hiện có một số khoảng version,
nên cần chạy lại test khi rebuild dependencies.

Sao lưu MySQL, Qdrant, MinIO và checkpoint SQLite cùng một mốc; tạm dừng thao tác
ghi API/worker/Beat khi chụp backup nhất quán. Giữ riêng `.env` và OAuth runtime
để phục hồi cấu hình. Chỉ đổi image code cũ chưa bảo đảm tương thích schema mới;
kiểm tra migration và backup trước khi rollback release.

Dừng container và giữ dữ liệu:

```bash
docker compose --profile demo --profile scheduler down
```

## Cấu hình phát triển trên máy hiện tại

Kiểm tra ngày 28/10/2026 cho thấy database hiện có ở `0014`, code yêu cầu `0015`,
worker chưa trả lời ping. Trước demo bằng cách chạy API/Next trực tiếp, cần áp dụng
migration và mở worker:

```bash
PYTHONPATH=. .venv/bin/alembic upgrade head
PYTHONPATH=. .venv/bin/celery -A src.workers.celery_app worker --pool=solo --loglevel=info
```

Phần này dành cho cách chạy API/Next trực tiếp trên máy. Profile Compose `demo`
tự chạy migration trong `prepare`. Kết quả kiểm chứng nằm trong
[báo cáo ngày 28/10](../testing/release-report-2026-10-28.md).

Thiết kế dựa trên [thứ tự khởi động Compose](https://docs.docker.com/compose/how-tos/startup-order/),
[Next standalone](https://nextjs.org/docs/app/api-reference/config/next-config-js/output)
và [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
