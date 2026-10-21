# Thư mời phỏng vấn — MAIL-01/02/03/04

## Phạm vi

Admin soạn một thư, duyệt nhiều thư, theo dõi hàng đợi và xem lịch sử.
Các màn dùng API mới bên dưới, dùng lại prompt `cv-rag-draft-interview-email` và Gmail hiện có.
Tạo/sửa/sinh nháp không gửi email. Chỉ bước xác nhận duyệt mới tạo thư trong hàng đợi.

- `/emails/compose`: chọn một ứng viên, nhập vị trí và lịch phỏng vấn.
- `/emails/bulk`: chọn tối đa 20 ứng viên có email, nhập thông tin chung.
- `/emails/batches/{batch_id}`: sửa/lưu/xem trước từng nháp, chọn người nhận và duyệt;
  sau duyệt chuyển thành màn tiến độ theo từng thư.
- `/emails/batches`: mở lại nháp và các đợt đã duyệt sau khi reload/đăng nhập lại.
- `/emails/history`: lịch sử từng thư, lọc tên/email/tiêu đề/trạng thái/ngày, mở nội dung đã lưu.
- Hồ sơ và màn phỏng vấn có lối sang **Soạn thư mời**.

## Chuẩn bị chạy

Tại thư mục gốc dự án:

```bash
.venv/bin/alembic upgrade head
```

Migration `0013` thêm `invitation_batches`, `invitation_drafts`, `invitation_deliveries`,
`invitation_recipient_guards` và `sent_emails.delivery_id`. Dữ liệu sent_emails cũ được giữ;
người dùng chỉ có quyền tester không truy cập được API/email UI.

Chạy MySQL và Redis; restart FastAPI để nhận router/schema mới. Chạy hoặc restart
Celery worker với code mới (macOS dùng pool solo):

```bash
PYTHONPATH=. .venv/bin/celery -A src.workers.celery_app worker --pool=solo --loglevel=info
```

Nếu chưa cấu hình OAuth Gmail, xem mục Gmail API trong README gốc. Có thể xác thực
và kiểm tra account trên máy local bằng lệnh sau; lệnh này không gửi email:

```bash
PYTHONPATH=. .venv/bin/python -c 'from src.ingestion.email_intake.gmail_client import GmailClient; GmailClient(); print("Gmail ready")'
```

Cần token có scope Gmail đang dùng, gồm `gmail.send` và quyền đọc để kiểm tra thư đã gửi.
Worker dùng `GmailClient(interactive=False)`: không mở browser xin OAuth trong background;
thiếu token/quyền/cấu hình thì trả trạng thái thất bại rõ ràng. Token/credential không gửi xuống FE.

Duyệt gửi trả `202`, nghĩa là yêu cầu đã được lưu; không có nghĩa Gmail đã gửi xong.
Worker xử lý hàng đợi. Nếu Redis tạm không kết nối, nháp/duyệt vẫn được lưu, UI có nút
**Đưa lại vào hàng đợi**. Nếu dự án đang chạy Celery beat, tác vụ drain quét outbox mỗi 30 giây.
Không cần bật beat để gửi bình thường; task được publish khi duyệt/requeue.

## API

Mọi endpoint yêu cầu bearer token admin. Response thành công có `Cache-Control: private, no-store`,
ngày giờ dùng UTC có offset. BFF Next dùng cookie HttpOnly, kiểm tra Origin trước mọi POST.

| Method | Endpoint | Chức năng |
| --- | --- | --- |
| POST | `/api/emails/batches` | Tạo nháp/đợt mới bằng request_id bền |
| GET | `/api/emails/batches?page=1&page_size=20` | Danh sách nháp/đợt, phân trang |
| GET | `/api/emails/batches/{batch_id}` | Nháp, tiến độ, từng delivery |
| POST | `/api/emails/drafts/{draft_id}` | Lưu subject/body theo revision |
| POST | `/api/emails/drafts/{draft_id}/generate` | Sinh/lưu nháp AI theo revision |
| POST | `/api/emails/batches/{batch_id}/dispatch` | Duyệt danh sách nháp đã lưu, tạo outbox, 202 |
| POST | `/api/emails/batches/{batch_id}/requeue` | Publish lại các delivery đã duyệt, 202 |
| POST | `/api/emails/deliveries/{delivery_id}/retry` | Thử lại thư đã thất bại rõ ràng, 202 |
| POST | `/api/emails/deliveries/{delivery_id}/reconcile` | Đọc Gmail để đối chiếu kết quả chưa rõ |
| GET | `/api/emails/history` | Lịch sử mail mới và legacy |
| GET | `/api/emails/history/{email_id}` | Nội dung đã lưu của một thư |

### Tạo nháp

```json
{
  "request_id": "33333333-3333-4333-8333-000000000001",
  "kind": "single",
  "candidate_ids": ["33333333-3333-4333-8333-000000000002"],
  "name": "Mời phỏng vấn Data Engineer",
  "position": "Data Engineer",
  "interview_details": "Vòng chuyên môn; 01/12/2026 10:00 UTC+7; trực tuyến; link đã cung cấp."
}
```

`kind=single` yêu cầu một ID; bulk 1–20 ID không trùng. `request_id` UUID được FE tái sử dụng
khi thử lại cùng thao tác tạo sau lỗi mạng; cùng key/nội dung trả lại cùng batch. Dùng key cho
nội dung khác bị chặn. Reload FE mất key trong bộ nhớ nhưng có thể mở lại batch đã tạo ở danh sách.
Người nhận được chụp từ email ứng viên; chưa có email vẫn tạo được nháp qua API nhưng không được duyệt gửi.

Response batch chứa:

- `batch_id`, `kind`, `name`, `position`, `interview_details`, `created_at`, `status`, `dispatch_error`.
- `drafts`: ID, candidate ID/tên, recipient, subject/body, revision, ready, previously_sent,
  is_generating và error_code. Email/ID ứng viên không được sửa thông qua API lưu nháp.
- `deliveries`: ID và snapshot người nhận/tiêu đề, status, attempts, Gmail ID, thời gian, error_code.
- `total`: số thư **đã được duyệt**, không phải số nháp; `counts` theo năm trạng thái.

Lưu nháp gửi `{expected_revision: 1, subject: "...", body: "..."}`;
sinh AI gửi `{expected_revision: 1}`. Subject 1–500 ký tự, không có CR/LF;
body plain text 1–15.000 ký tự. Lưu thành công tăng revision. AI lỗi không thay nội dung đã lưu.
Khi tab khác sửa hoặc đợt đã duyệt, API chặn ghi đè. Thay nội dung sau gửi cần tạo nháp mới.

### Duyệt gửi

```json
{
  "confirmed": true,
  "allow_previous": false,
  "drafts": [{"draft_id": "33333333-3333-4333-8333-000000000003", "revision": 2}]
}
```

Chỉ các nháp trong danh sách này được gửi. Server kiểm tra revision, nội dung, địa chỉ email,
email hiện tại của ứng viên, trùng địa chỉ, thư đang chờ/chưa rõ kết quả và lịch sử gửi thành công.
Nếu từng gửi, admin phải đánh dấu xác nhận gửi thêm (`allow_previous=true`). Cờ này không cho phép
bỏ qua một delivery đang queued/sending/unknown.

Duyệt cùng payload nhiều lần trả cùng delivery; payload khác cho đợt đã duyệt bị chặn.
Một draft chỉ có tối đa một delivery (unique constraint). Server đóng băng nội dung đã duyệt;
không nhận recipient/subject/body tùy ý tại endpoint dispatch.

### Trạng thái và kết quả chưa rõ

| Trạng thái thư | Nghĩa |
| --- | --- |
| queued | Đã duyệt, chờ worker |
| sending | Worker đã ghi nhận quyền xử lý trước khi gọi Gmail |
| success | Gmail trả message ID hoặc đối chiếu tìm thấy thư trong Sent |
| failed | Chưa gọi send vì cấu hình/quyền/email thay đổi, hoặc Gmail trả từ chối rõ ràng |
| unknown | Timeout/lỗi không xác định, worker gián đoạn hoặc thiếu kết quả sau send |

Batch là draft/queued/sending/completed/needs_attention; tiến độ tổng hợp từ delivery thật,
không đếm riêng log sau gửi để suy luận tổng số dự kiến.

- Claim queued → sending dùng update có điều kiện và commit trước Gmail; task bị giao lại
  không gửi thêm một delivery sending/success/unknown.
- Các lần duyệt được phối hợp bằng khóa DB theo địa chỉ người nhận; cùng người/email đang có
  delivery chưa ngã ngũ bị chặn giữa các đợt. Header Message-ID ổn định giúp đối chiếu Gmail;
  header này **không** được coi là cơ chế idempotency do Gmail bảo đảm.
- Lỗi lúc ghi log sau Gmail không dẫn đến tự gửi lại. Sending quá 10 phút được hiển thị unknown khi đọc tiến độ (không cần beat);
  drain cũng ghi trạng thái này vào DB. FE không tự POST lại khi timeout.
- Với unknown, **Kiểm tra Gmail** tìm thư trong Sent theo Message-ID. Tìm thấy thì success;
  chưa thấy vẫn unknown, không biến thành failed để mở đường gửi lại.
- Retry chỉ đưa failed về queued; các trạng thái khác trả lại trạng thái hiện có và không gửi lại.
  Người duyệt ban đầu phải còn quyền; nếu bị khóa/mất quyền, tạo và duyệt đợt mới.
- Worker kiểm tra account duyệt vẫn active/admin và email hiện tại trước từng thư.

Không thể chứng minh exactly-once chỉ bằng Gmail API và transaction database. Thiết kế chọn
ngừng gửi lại khi kết quả mơ hồ, để admin đối chiếu trước; không tự tạo một thư mới để vượt trạng thái unknown.

### Lịch sử

`page`, `page_size`, `q` (tên/email/subject, tìm literal), `status`, `candidate_id`, `batch_id`,
`date_from`, `date_to`. Khoảng ngày theo giờ Việt Nam (UTC+7); response timestamp UTC.
List không trả body, detail mới trả body. Raw lỗi Gmail/SQL/stacktrace cũ không đưa xuống trình duyệt.

Mỗi delivery là một dòng lịch sử, cập nhật kết quả mới nhất khi retry; số lần xử lý nằm ở delivery.attempts.
Log legacy vẫn đọc được. `sent_at` ở dòng queued là thời điểm ghi nhận yêu cầu, chưa phải thời điểm Gmail gửi.
Thư legacy có batch_id nhưng không có delivery mới không được liên kết sang màn batch mới không tồn tại.

## Kiểm chứng

```bash
LANGCHAIN_TRACING_V2=false LANGSMITH_TRACING=false OPS_ENABLED=false \
  .venv/bin/python -m pytest tests/api/test_emails.py -q
cd frontend
npm run test:e2e -- tests/emails.spec.ts
```

Test dùng SQLite/Gmail/model giả lập: không gửi thư thật. Bao gồm gửi một người và một phần danh sách,
revision, replay, địa chỉ trùng, người từng nhận, timeout/unknown, reconcile, retry thất bại rõ ràng,
worker nhận task hai lần, DB lỗi sau send, queue gián đoạn, khóa người duyệt, history legacy và migration up/down.

Trên hệ thống thật, trước hết lưu nháp, reload để kiểm tra bền, xem preview và hủy popup xác nhận để kiểm tra
chưa có thư gửi. Khi chủ động kiểm tra gửi thật, dùng một ứng viên với địa chỉ nhận do bạn kiểm soát,
xác nhận đúng nội dung/người nhận rồi đối chiếu cả trang tiến độ, lịch sử và Gmail Sent.

## Giới hạn so với prototype

Nội dung email plain text, không có rich HTML editor/attachment, email test riêng, lịch nhắc hẹn,
export CSV/Excel hay nút tạm dừng/hủy cả batch. Những nút demo đó không được hiển thị như chức năng thật.
Phần hiện có hoàn thành luồng soạn/lưu/preview/duyệt/gửi đơn lẻ và hàng loạt, tiến độ, đối chiếu lỗi và lịch sử.
