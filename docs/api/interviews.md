# Câu hỏi phỏng vấn — INT-01

Admin xem/sinh/xóa bộ câu hỏi theo ứng viên. API dùng bảng `interview_questions`
và prompt LangSmith hiện có, không cần migration. Sinh câu hỏi gọi Gemini thật.

| Method | Endpoint | Kết quả |
| --- | --- | --- |
| GET | `/api/candidates/{candidate_id}/interview-questions` | Bộ đang lưu và trạng thái sinh |
| POST | `/api/candidates/{candidate_id}/interview-questions/generate` | Sinh, kiểm tra, thay bộ cũ và trả bộ đã lưu |
| DELETE | `/api/candidates/{candidate_id}/interview-questions?expected_revision=...` | Xóa bộ đúng phiên bản và trả bộ rỗng |

UUID và token admin bắt buộc; tester nhận 403. Mọi hàm service HTTP kiểm tra admin,
trước khi lưu sau cuộc gọi AI cũng kiểm tra lại phiên. Response thành công có
`Cache-Control: private, no-store`; lỗi dùng envelope/request ID chung.

## Response

```json
{
  "candidate_id": "33333333-3333-4333-8333-000000000001",
  "items": [{
    "id": 123,
    "question": "Bạn thiết kế pipeline dữ liệu như thế nào?",
    "category": "Technical",
    "cv_section": "Dự án",
    "evidence_quote": "Built Python and SQL pipelines."
  }],
  "revision": "<chuỗi hex SHA-256 dài 64 ký tự>",
  "has_cv": true,
  "is_generating": false
}
```

Nhóm câu hỏi: `Technical`, `System Design`, `Soft Skill`. `items=[]` nếu chưa có bộ đã lưu;
GET vẫn hoạt động với ứng viên chưa có nội dung CV (`has_cv=false`). Revision là dấu vân tay
của CV và bộ đang lưu; lấy giá trị thật từ GET để gửi mutation. Đây không phải ID tác vụ
hay idempotency key bền vững.

## Sinh và thay bộ cũ

Body JSON chỉ chấp nhận:

```json
{
  "max_questions": 8,
  "expected_revision": "<revision từ GET>",
  "replace_existing": false
}
```

- `max_questions`: integer 3–15, mặc định 8; không nhận string/bool.
- `expected_revision`: bắt buộc. CV hoặc bộ câu hỏi thay đổi thì trả 409 trước khi sinh
  hoặc ngay trước lưu; kết quả cũ không bị ghi đè.
- `replace_existing=true`: cần khi đã có câu hỏi; FE hiển thị xác nhận trước khi gửi.
- Evidence được so với CV sau chuẩn hóa khoảng trắng/hoa thường; bỏ evidence rỗng,
  nội dung không khớp, câu hỏi/section rỗng và câu hỏi trùng; lưu tối đa số được yêu cầu.
- Nếu không có câu hợp lệ, thử sinh lại một lần. Vẫn không có thì trả 422 và giữ nguyên bộ cũ.
  Số câu thực tế có thể ít hơn yêu cầu sau khi kiểm tra; FE hiển thị số thực tế.
- Gemini lỗi, quota, timeout, phiên bị thu hồi hoặc transaction thất bại không được
  xóa bộ cũ. Thay thế là một transaction sau khi đã có kết quả hợp lệ.
- Trong cùng process, sinh/xóa đồng thời cho cùng ứng viên bị chặn 409 `INTERVIEW_BUSY`;
  GET vẫn đọc được bộ đang lưu và cờ `is_generating`.

## Xóa

Gửi revision hiện tại bằng query `expected_revision`; không cần JSON body. FE có bước
xác nhận rõ tên hành động. Chỉ xóa bộ câu hỏi của ứng viên đã chọn. Sau thành công
trả response có `items=[]` và revision tương ứng. Bộ rỗng có thể xóa lại an toàn nếu revision khớp.

## Trạng thái lỗi

| HTTP | Code | Ý nghĩa |
| --- | --- | --- |
| 401 / 403 | AUTHENTICATION_REQUIRED / FORBIDDEN | Phiên/quyền không hợp lệ |
| 404 | CANDIDATE_NOT_FOUND | Không có ứng viên |
| 409 | INTERVIEW_BUSY | Một yêu cầu sinh/xóa đang chạy cho ứng viên |
| 409 | STALE_INTERVIEW_SET | CV hoặc bộ câu hỏi đã đổi; cần GET lại |
| 409 | INTERVIEW_REPLACE_REQUIRED | Chưa xác nhận thay bộ đang có |
| 422 | CANDIDATE_HAS_NO_CV | Không có nội dung CV |
| 422 | NO_VALID_INTERVIEW_QUESTIONS | Không sinh được câu có evidence hợp lệ |
| 422 | VALIDATION_ERROR | JSON/query/path sai |
| 503 / 504 | DEPENDENCY_UNAVAILABLE / DEPENDENCY_TIMEOUT | Lỗi dịch vụ phụ thuộc hoặc timeout |

FE không tự gửi lại POST/DELETE. Sau lỗi, FE GET lại bộ đang lưu; nếu còn
`is_generating=true` sẽ đọc trạng thái mỗi 2 giây và khóa mutation. Timeout HTTP
không chứng minh AI đã dừng. Dữ liệu cũ vẫn có thể xuất hiện trong khi đang sinh.

## Chạy và giới hạn

Tiếp tục chạy một process API (`--workers 1`) như cấu hình checkpoint hiện có.
Khóa/cờ sinh đang chạy nằm trong process, không phải durable job; không chạy nhiều
writer API/Streamlit cùng lúc cho bộ câu hỏi. Muốn triển khai nhiều worker cần hàng đợi,
trạng thái job bền vững và cơ chế phối hợp giữa process.

Bản này sinh theo CV; chưa có chọn JD, tỷ lệ nhóm/độ khó, Green/Red Flags,
chỉnh sửa/ghi chú hay xuất PDF/Word. Không hiển thị các trường demo đó trong sản phẩm.

## Kiểm thử

```bash
LANGCHAIN_TRACING_V2=false LANGSMITH_TRACING=false OPS_ENABLED=false \
  .venv/bin/python -m pytest tests/api/test_interviews.py tests/test_question_generator.py -q
```

Test dùng SQLite và model giả lập, không gọi Gemini/LangSmith thật. Đã kiểm tra giữ bộ cũ khi provider lỗi, evidence không hợp lệ, CV thay đổi, phiên bị thu hồi và lỗi ghi database sau khi bắt đầu thay thế (rollback).

Swagger: đăng nhập admin → GET bộ câu hỏi để lấy revision → POST generate → GET lại →
POST với `replace_existing=true`/revision mới → DELETE với revision mới.
Kiểm tra 403 bằng tester, 422 với số câu 2/16, giữ bộ cũ khi sinh không hợp lệ/lỗi provider.

Giao diện: mở hồ sơ → **Tạo câu hỏi phỏng vấn** hoặc `/interviews` → chọn người →
chọn 3–15 câu → **Sinh bộ câu hỏi** → lọc nhóm/sao chép → tải lại kiểm tra lưu bền →
thử xác nhận/hủy sinh lại và xóa. Cần Gemini/LangSmith/MySQL sẵn sàng để nghiệm thu với CV thật.
