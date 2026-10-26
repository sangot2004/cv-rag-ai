# Đề xuất tối ưu và experiment

Trang admin: `/ops/optimization`, mở từ System Ops. Có cấu hình đang chạy, tạo đề
xuất thủ công hoặc AI phân tích, so sánh cấu hình, experiment chạy nền, báo cáo,
Approve và rollback về cấu hình từng được duyệt hoặc mặc định.

## Khởi động

Bật MySQL và Redis, chạy migration, rồi khởi động lại FastAPI và worker:

```sh
PYTHONPATH=. .venv/bin/alembic upgrade head
PYTHONPATH=. .venv/bin/python -m uvicorn src.api.app:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Terminal khác:

```sh
PYTHONPATH=. .venv/bin/celery -A src.workers.celery_app worker --pool=solo --loglevel=info
```

Frontend: `cd frontend && npm run dev`.
Migration 0015 tạo `ops_experiment_jobs`; không xóa dữ liệu hiện có.
Migration chưa được tự áp dụng lên MySQL trong lần triển khai này.

## Kiểm thử bằng dữ liệu thật

1. Đăng nhập admin, mở System Ops → Đề xuất tối ưu và experiment.
2. Tạo đề xuất model/prompt/cache. Prompt phải là commit LangSmith cố định, 8–40
   ký tự hex. Model trống dùng model mặc định của hệ thống. Retrieval giữ nguyên.
3. Chọn đề xuất và dataset LangSmith có `inputs.raw_text`, outputs hợp lệ CVSchema.
4. Bấm Chạy experiment và xác nhận gọi AI. Job chuyển queued → running → completed
   hoặc failed; FE đọc trạng thái mỗi 5 giây. Completed nghĩa chạy xong, không
   đồng nghĩa báo cáo đạt điều kiện duyệt.
5. Đọc chất lượng, số mẫu, token, tổng latency và chi phí baseline/proposal.
   Thiếu usage/giá hiển thị rõ; chi phí free tier bằng 0 không chứng minh tiết kiệm tiền.
6. Approve chỉ áp dụng khi backend kiểm tra report passed và baseline/config vẫn
   khớp. Nếu cấu hình đang chạy đã thay đổi, phải chạy lại experiment.
7. Rollback chọn cấu hình đã được duyệt, hoặc nút về mặc định; cần xác nhận.
8. Redis lỗi: job vẫn queued, có QUEUE_UNAVAILABLE; dùng Kiểm tra / khôi phục.
   Worker mất giữa chừng: job có thể còn running. Khi không còn giữ khóa, khôi phục
   đánh dấu failed/WORKER_INTERRUPTED; người dùng chủ động tạo experiment mới.
   Không tự chạy lại model khi trạng thái kết quả chưa rõ.
9. Tester phải bị chặn ở cả giao diện và API.

## Contract và giới hạn

- `GET /api/ops/optimization`: active config, tối đa 100 proposal và 100 job mới nhất.
- `POST /api/ops/optimization`: cấu hình extraction, tạo proposal.
- `POST /api/ops/optimization/analyze`: `{confirmed:true}`, AI phân tích usage đồng bộ;
  có thể tiêu thụ token. Rationale trả về và hiển thị trong phiên UI.
- `POST /api/ops/optimization/{id}/experiment`: `{confirmed:true,dataset:"..."}`, trả 202.
- `POST /api/ops/optimization/{id}/approve`, `/{id}/rollback`, `/defaults`:
  `{confirmed:true}`.
- `POST /api/ops/experiments/{job_id}/recover`: `{confirmed:true}`.

Tất cả yêu cầu admin; BFF kiểm tra origin cho mutations. Celery chỉ nhận job ID,
không lưu bearer token trong broker. Worker kiểm tra creator vẫn active/admin khi
bắt đầu. Khóa SQL theo proposal bảo vệ experiment/approve/rollback cả đường CLI.
Job được claim một lần; khi worker crash, cần thao tác khôi phục thủ công.

Runner hiện có chỉ kiểm chứng extraction; quality là so khớp đáp án bằng code.
Runner gọi model trực tiếp, chưa đo lợi ích Redis cache bằng thực nghiệm. Quy tắc
hiện có cho phép đề xuất chỉ bật cache đạt nếu chất lượng đạt dù chưa đo cache hit.
FE ghi rõ giới hạn này. Không có routing độ khó, retrieval experiment hay LLM judge.
Dữ liệu báo cáo không chứa nội dung CV/prompt; có ID mẫu và tên project LangSmith.

Kiểm thử offline: `tests/api/test_ops_workflow.py`, `tests/test_optimization.py`;
browser mock: `frontend/tests/optimization.spec.ts`. Chưa chạy experiment gọi model
thật trong quá trình triển khai.
