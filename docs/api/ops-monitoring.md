# System Ops — giám sát usage

Đã triển khai trang admin `/ops` (OPS-01), qua BFF `/api/backend/ops/dashboard`.
Không cần migration mới. Khởi động lại FastAPI và chạy frontend như thông thường.
Chức năng chỉ đọc dữ liệu SQL; mở trang không gọi model, Redis, MinIO hay gửi email.

## API

`GET /api/ops/dashboard` — Bearer session của admin, `Cache-Control: private, no-store`.
Tester nhận 403, thiếu/phiên hết hạn nhận 401. Lỗi DB trả lỗi chuẩn 503, không lộ DSN.

Query:

| Trường | Mặc định | Ý nghĩa |
| --- | --- | --- |
| days | 7 | 1, 7 hoặc 30 ngày gần nhất |
| module | bỏ trống | Module chính xác |
| model | bỏ trống | Model chính xác |
| status | bỏ trống | Trạng thái chính xác, lấy options từ API |
| page | 1 | Trang log, từ 1 đến 100000 |
| page_size | 25 | 1–100 |
| alerts_only | false | Chỉ lọc bảng log cảnh báo, không đổi KPI/biểu đồ |

Một response gồm `start`, `end`, `summary`, `daily`, `breakdown`, `options`,
`alerts`, `dlq_count`, `logs`. Gộp thành một endpoint để các khối sử dụng chung
khoảng thời gian và bộ lọc. Tổng hợp, sắp xếp và phân trang tại SQL; không tải toàn
bộ logs vào Python/pandas. Percentile nội suy tuyến tính trên thứ tự độ trễ trong
SQL, chỉ lấy tối đa hai giá trị cho mỗi percentile. Số nhóm breakdown/options phụ
thuộc số model/module đã ghi nhận. Khi dữ liệu lớn cần đo query latency/index
trước khi bổ sung cơ chế rollup.

- Khoảng `[start, end)` tính theo UTC. DATETIME trong DB được coi là UTC;
  timestamp trả về có timezone. Ngày đầu/cuối có thể chỉ chứa một phần ngày.
- `calls`: số bản ghi AI call/attempt; không phải số câu hỏi hay số CV.
- Token là tổng input/output đã ghi nhận; `missing_usage_calls` đếm call thiếu
  một trong hai. Không cộng cached/reasoning thêm vào tổng.
- `estimated_cost_usd`: tổng chi phí đã định giá, **null nếu không có call có giá**.
  `priced_calls` cho biết độ đầy đủ. Bằng 0 chỉ có nghĩa tổng phần đã định giá bằng 0;
  luôn hiển thị số call thiếu giá bên cạnh. Áp dụng nhất quán KPI, nhóm, ngày, log.
  Đây là ước tính lưu tại lúc gọi, không tính lại log cũ khi đổi cấu hình giá.
- `median_ms` và `p95_ms`: độ trễ mỗi call, null khi không có calls.
- `failover_calls`: số call có attempt > 1; không phải số request bị lỗi.
- Rule alerts: status error, latency > `OPS_LATENCY_ALERT_MS` (15000), hoặc
  input+output > `OPS_TOKEN_ALERT` (20000). ENV hỏng/âm/NaN dùng mặc định.
- DLQ đếm toàn hệ thống, không theo bộ lọc usage, vẫn trả khi không có usage.
- Options lấy từ khoảng thời gian, trước bộ lọc module/model/status.
- Logs sort created_at DESC, id DESC. Các lần tải dùng cửa sổ thời gian mới,
  nên log mới có thể dịch chuyển phân trang; không bảo đảm snapshot qua nhiều request.
- Log detail chứa metadata usage trong allowlist; không trả CV, prompt, raw error,
  API key, đường dẫn storage hay nội dung hội thoại.

## Giao diện

Bộ lọc/số trang nằm trong URL. Refresh thủ công và lúc quay lại trang theo query
policy của ứng dụng; hiển thị thời điểm lấy dữ liệu. Lỗi refresh giữ dữ liệu cũ
kèm thông báo, không biến thành số 0. Biểu đồ có thể chọn call/token/chi phí và bấm
hoặc dùng bàn phím để xem giá trị mỗi ngày. Ngày thiếu toàn bộ giá hiển thị `?`;
ngày có một phần dữ liệu dùng cột sọc và ghi số call thiếu dữ liệu.

Link DLQ mở `/ingestion/jobs?status=dlq`. Log có dialog chi tiết và hỗ trợ Escape.
Menu chỉ hiện cho admin; API vẫn tự kiểm tra quyền. Query cache gắn user ID và được
xóa khi đổi phiên. Không có thao tác thay đổi cấu hình trên trang này.

## Kiểm thử thủ công

1. Restart FastAPI, mở frontend, đăng nhập admin, chọn **System Ops**.
2. Chọn 1/7/30 ngày, module/model/status, bấm **Áp dụng**; kiểm tra URL và số liệu.
3. Gọi AI hoặc xử lý CV, quay lại Ops **Làm mới**. Cần `OPS_ENABLED=true` khi phát
   sinh usage; trang không backfill lịch sử trước khi bật telemetry.
4. Nếu free tier có usage đầy đủ và giá bằng 0, thấy `$0.000000`; model chưa có giá
   phải là **Chưa xác định**, không coi là tiết kiệm tiền.
5. Bấm **Chi tiết**, kiểm tra phiên bản giá, tokens và attempt; Escape đóng dialog.
6. Chọn **Chỉ xem cảnh báo**, kiểm tra bảng log thay đổi nhưng KPI vẫn giữ bộ lọc gốc.
7. Mở **Kiểm tra tác vụ lỗi**, xác nhận filter DLQ; không tự retry job.
8. Đăng nhập tester: `/ops` chặn giao diện; gọi endpoint trực tiếp phải 403.
9. Thử chiều rộng 390px: KPI xếp dọc, bảng/biểu đồ cuộn trong khung.

Automated checks:

```sh
.venv/bin/python -m pytest tests/api/test_ops_monitoring.py -q
cd frontend
npm run lint
npm run typecheck
npm run test:e2e -- tests/ops.spec.ts
```

Backend test dùng SQLite; browser dùng mock API, không gọi model thật.

## Phần tiếp theo

Đã triển khai màn optimization/experiment/approve/rollback tại `/ops/optimization`;
xem [hướng dẫn](ops-optimization.md). Các luồng
Streamlit/CLI hiện có vẫn giữ nguyên. Backend monitoring service mới độc lập với
Streamlit; chưa thay dashboard Streamlit cũ. Chưa đo Redis cache hit, RPM/TPM,
retrieval cache, chi phí toàn bộ một CV hay latency toàn bộ request. Không đưa
số giả của prototype vào dashboard.

## Kết quả kiểm tra triển khai 23/10/2026

- 4 tests API trên SQLite: đạt (quyền, filters, chi phí 0/null, percentile,
  redaction, phân trang, empty và DLQ).
- 3 tests trình duyệt Chrome với mock: đạt (filter qua BFF, dialog, phân trang,
  free/unknown cost, empty, lỗi/khôi phục, mobile, tester bị chặn).
- ESLint, TypeScript và production build: đạt.
- Đã xem ảnh desktop/mobile từ browser test.
- Smoke chỉ đọc trên MySQL thật chưa chạy thành công: kết nối báo mã 2003.
  Cần bật dịch vụ MySQL rồi nghiệm thu bằng dữ liệu thật.
