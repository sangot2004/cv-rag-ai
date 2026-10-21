# Quản trị và tiếp nhận CV

## Phạm vi đã triển khai

- `/admin/departments`: tìm kiếm/phân trang, tạo phòng ban, số vị trí và số CV;
  liên kết sang vị trí và danh sách ứng viên theo phòng ban.
- `/admin/postings`: tìm kiếm/phân trang, lọc phòng ban, tạo vị trí, số CV và liên kết ứng viên.
- `/admin/users`: tìm kiếm/phân trang, lọc quyền/phòng ban/trạng thái, tạo admin/tester,
  khóa/mở tài khoản bằng xác nhận. Tester bắt buộc có phòng ban.
- Trong hồ sơ ứng viên: gán, đổi hoặc bỏ vị trí tuyển dụng, xác nhận ảnh hưởng đến
  phạm vi phòng ban. Kiểm tra `expected_posting_id` để tránh ghi đè thay đổi của admin khác.
- `/ingestion/upload`: kéo thả/chọn tối đa 10 PDF/lượt; chọn phòng ban rồi vị trí;
  gửi từng file, hiển thị tiến độ truyền byte, kết quả tiếp nhận riêng và link tác vụ.
- `/ingestion/jobs` và `/ingestion/jobs/[jobId]`: lọc tên/trạng thái/nguồn,
  xem thời điểm/số lần xử lý/kết quả, mở ứng viên, đưa lại hàng đợi/thử lại có điều kiện.

Tất cả API và màn riêng trên chỉ dành cho admin. Tester tiếp tục tra cứu trong chat
theo phòng ban đã cấp. Khóa và mở tài khoản đều thu hồi các phiên cũ; lịch sử giữ nguyên.
Không cho admin tự thay đổi trạng thái chính mình. Mật khẩu mới 12–256 ký tự;
không có hash, session token hay mật khẩu trong DTO quản trị.

## Chạy local

Tại thư mục gốc:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/alembic upgrade head
PYTHONPATH=. .venv/bin/uvicorn src.api.app:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Terminal khác, tại thư mục gốc:

```bash
PYTHONPATH=. .venv/bin/celery -A src.workers.celery_app worker --pool=solo --loglevel=info
```

Terminal frontend:

```bash
cd frontend
npm run dev
```

Migration **0014** thêm nullable metadata cho `ingestion_jobs`: vị trí nhận,
người upload, hash file duy nhất, thời điểm bắt đầu, mã lỗi và lỗi đưa hàng đợi.
Không sửa CV/tài khoản/tác vụ cũ; hash file của tác vụ cũ không được backfill.
Cần khởi động lại FastAPI và worker sau khi cập nhật code/migration.

Upload cần MySQL, MinIO và Redis. Xử lý đầy đủ cần thêm Qdrant, cấu hình model,
embedding và prompt LangSmith như pipeline hiện có. Không cần Gmail OAuth cho
upload qua web; Gmail vẫn cần OAuth khi dùng nguồn email/gửi thư.

## HTTP contract

Các trang danh sách nhận `page` (mặc định 1), `page_size` (mặc định 20, tối đa 100),
`q` (tối đa 200 ký tự). Kết quả `{items,total,page,page_size,has_next}`.
GET/POST đều yêu cầu Bearer session và `Cache-Control: private, no-store`.

| Method | Path | Dữ liệu/ý nghĩa |
| --- | --- | --- |
| GET | `/api/admin/departments` | Danh sách, `posting_count`, `cv_count` |
| POST | `/api/admin/departments` | `{department_name}`; 201 |
| GET | `/api/admin/postings` | Thêm filter `department_id`; gồm vị trí đang/ngừng tuyển |
| POST | `/api/admin/postings` | `{department_id,position_title}`; 201 |
| GET | `/api/admin/users` | Thêm `department_id`, `role`, `active` |
| POST | `/api/admin/users` | `{username,password,role,department_id}`; 201 |
| POST | `/api/admin/users/{user_id}/active` | `{active:true/false}`; thu hồi phiên |
| POST | `/api/candidates/{candidate_id}/posting` | `{posting_id,expected_posting_id}`; cả hai có thể null |
| GET | `/api/ingestion/capabilities` | Giới hạn file thực tế, regex tên file và tên ví dụ |
| POST | `/api/ingestion/uploads` | Multipart: đúng một `file` và một `posting_id`; 202 trả JobView |
| GET | `/api/ingestion/jobs` | Thêm `status`, `source_type=web_upload/email` |
| GET | `/api/ingestion/jobs/{job_id}` | JobView, mã lỗi an toàn, liên kết candidate nếu có |
| POST | `/api/ingestion/jobs/{job_id}/retry` | `{confirmed:true}`; 202 trả trạng thái đọc lại |

### Ví dụ upload qua Swagger

`POST /api/ingestion/uploads` → **Try it out** → chọn PDF tại `file` → nhập UUID
vị trí có thật tại `posting_id` → **Execute**. Header Authorization dùng phiên admin.
Tên mặc định: `NguyenVanA_DataEngineer_CV.pdf`; PDF từ 20 KB đến 50 MB, tối đa 10 trang.
Giới hạn thực tế đọc từ capabilities; trần HTTP/BFF là 50 MiB + 64 KiB multipart overhead.
Tên không được chứa đường dẫn/ký tự điều khiển. Backend kiểm tra extension, regex,
dung lượng, header PDF, integrity, mã hóa và số trang. HTTP 202 chỉ xác nhận tiếp nhận.

### Trạng thái

| DB status | Hiển thị | Hành vi |
| --- | --- | --- |
| pending | Chờ xử lý | File và tác vụ đã lưu; có thể đưa lại hàng đợi |
| processing | Đang xử lý | Worker đang parse/OCR/classify/extract/embed/index |
| failed | Chờ thử lại | Lỗi tạm thời; worker lên lịch thử lại, giới hạn số lần trong DB |
| dlq | Cần kiểm tra | Hết số lần thử; admin có thể mở lượt thử mới |
| rejected | Bị từ chối | Không thử lại file cũ; kiểm tra nội dung/nộp bản sửa |
| indexed | Đã xử lý | SQL và bước index đã hoàn thành, có liên kết ứng viên |

Attempts đếm lần **bắt đầu xử lý** trong lượt, kể cả lần thành công. Mở lượt mới
từ DLQ hoặc khôi phục worker đã dừng đặt lại attempts về 0; đây không phải lịch sử
attempt chi tiết. JobView không trả bucket/key MinIO, hash file, source reference,
raw exception hoặc thông tin xác thực.

### Chống trùng và khôi phục

- File mới được nhận qua web có SHA256 trong unique `file_hash`. Upload lại cùng
  byte và cùng vị trí trả cùng tác vụ, không tự gọi AI/đưa hàng đợi lần nữa.
- Cùng file nhưng khác vị trí trả 409 `FILE_ALREADY_ASSIGNED`: kiểm tra tác vụ cũ
  hoặc gán lại hồ sơ khi đã tạo. Tên file khác không bỏ qua kiểm tra hash.
- PDF khác byte nhưng cùng text được phát hiện ở pipeline. CV cũ/tác vụ email
  chưa có file hash cũng được kiểm tra trùng text khi xử lý.
- File lưu MinIO và job commit trước khi publish Celery. Redis lỗi giữ job pending
  và `dispatch_error=QUEUE_UNAVAILABLE`; admin sửa Redis rồi **Đưa lại vào hàng đợi**.
- Worker dùng MySQL advisory lock theo job, bỏ qua delivery trùng/đã hoàn tất.
  Một khóa toàn pipeline tuần tự hóa ingestion để kiểm tra trùng text giữa các job.
  Worker bận khóa này sẽ chờ qua retry, không tiêu hao attempt xử lý.
- API khôi phục dùng cùng khóa job. Nếu worker còn giữ khóa, trả 409 `JOB_RUNNING`.
  Nếu worker đã dừng/mất process và khóa đã được MySQL giải phóng, admin có thể
  khôi phục job processing. Không dùng thời gian chờ của FE để kết luận worker chết.
- Candidate UUID ổn định theo job. Nếu Qdrant đã ghi mà SQL commit lỗi, lần thử sau
  xóa/thay points của cùng candidate UUID trước khi upsert, tránh tạo candidate ID
  mới cho cùng tác vụ. SQL candidate và trạng thái indexed commit cùng transaction.
- Vị trí admin chọn được giữ xuyên pipeline; tự match theo nội dung chỉ dùng khi
  tác vụ không có vị trí chỉ định (ví dụ email cũ). Không gọi AI để quyết định quyền.
- Đổi vị trí ứng viên cập nhật scope SQL; retrieval lấy tập ID được phép từ SQL
  hiện tại trước khi tìm vector/BM25. Không cần chép department vào vector payload.

SQLite chỉ dùng test offline; khóa fallback trong SQLite chỉ đồng bộ thread cùng
process. Triển khai thật dùng MySQL. Cần restart **mọi worker cũ** để toàn bộ worker
cùng áp dụng quy tắc khóa. Không chạy các script cũ ghi pipeline song song khi nâng cấp.
BM25 vẫn làm mới theo lịch hiện có; vector/SQL dùng dữ liệu đã commit.

## Kiểm tra thủ công theo thứ tự

1. Admin → Phòng ban → tạo phòng ban mới; thấy dòng mới, số CV = 0.
2. **Xem vị trí** → tạo vị trí; chỉ nằm trong phòng ban vừa chọn; chưa có CV là trạng thái trống.
3. Tài khoản → tạo tester thuộc phòng ban mới; đăng nhập được ở profile trình duyệt khác.
4. Admin khóa tester → tester thao tác/tải lại bị từ chối. Mở lại → cần đăng nhập mới.
   Hội thoại cũ vẫn còn. Nút tự khóa admin hiện tại bị vô hiệu hóa và API cũng chặn.
5. Upload → chọn phòng ban/vị trí → nộp PDF hợp lệ. Nhận link tác vụ, không báo indexed sớm.
6. Worker chạy → tác vụ chuyển indexed → mở hồ sơ; vị trí trùng lựa chọn lúc upload.
7. Tester tra cứu trong chat thấy CV phòng ban mình; tester phòng ban khác không thấy.
8. Upload lại file với cùng vị trí → cùng job ID, không có CV mới.
9. Hồ sơ ứng viên → gán sang vị trí khác → xác nhận → bộ lọc và phạm vi tra cứu mới áp dụng.
10. File sai tên/hỏng/quá số trang → báo lỗi riêng, không cản các file hợp lệ trong lượt.
11. Nếu cần kiểm tra lỗi queue: dừng Redis, upload → job vẫn lưu pending; mở Redis,
    vào chi tiết job, xác nhận đưa lại hàng đợi → worker xử lý cùng job.
12. Không retry tác vụ đang chạy: API trả JOB_RUNNING. Dừng hẳn worker trước khi
    dùng khôi phục job processing; không đổi trực tiếp status trong DB để ép chạy.

## Test tự động

```bash
LANGCHAIN_TRACING_V2=false LANGSMITH_TRACING=false OPS_ENABLED=false \
  .venv/bin/python -m pytest tests/api/test_management_ingestion.py -q
```

```bash
cd frontend
npm run typecheck
npm run lint
npm run test:e2e -- tests/management-ingestion.spec.ts
npm run build
```

Các test dùng PDF sinh trong bộ nhớ, SQLite và dịch vụ/model giả lập. Browser test
đi qua BFF thật nhưng backend mock. Không gửi email và không dùng CV thật/gọi AI thật.

## Giới hạn bản đầu

Chưa có sửa/xóa/hợp nhất phòng ban, đóng/sửa vị trí, đổi quyền/phòng ban tài khoản,
reset mật khẩu qua web, audit trail thay đổi scope, lịch sử attempt chi tiết hoặc
pipeline progress phần trăm. Reset mật khẩu tiếp tục dùng CLI. Không có công cụ
dọn object/point còn lại sau sự cố giữa các hệ lưu trữ; các ID ổn định và bước thay
points giúp retry phục hồi, nhưng SQL/MinIO/Qdrant không có distributed transaction.
