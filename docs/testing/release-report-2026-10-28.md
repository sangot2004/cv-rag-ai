# Báo cáo kiểm chứng — 28/10/2026

Phạm vi được duyệt: hoàn thiện giao diện, kiểm thử toàn luồng, admin/tester và chuẩn
bị demo. Không thêm thao tác chuyển JD sang phỏng vấn hoặc chọn hàng loạt từ chat.

## Thay đổi

- Trang loading, error boundary và 404 tiếng Việt, có nút tiếp tục/tải lại.
- Menu mobile đóng khi dùng các liên kết điều hướng, kể cả bàn phím Enter.
- Build Next standalone, Dockerfile frontend và image API/worker chạy non-root.
- Hai cấu hình Compose đã gộp vào `docker-compose.yml`: mặc định chạy dữ liệu,
  profile `demo` chạy ứng dụng, `scheduler` bật Beat. Dùng `.env` và `.env.example`
  hiện có; giữ tên container/volume cũ và cập nhật hướng dẫn chuyển checkpoint.
- Compose demo có MySQL/Redis/MinIO/Qdrant, migration/khởi tạo trước API, worker và
  Caddy HTTPS; volume bền và scheduler Gmail tùy chọn.
- `.dockerignore` loại env, OAuth, database local, CV và thư mục build khỏi image.
- Script kiểm tra readiness chỉ đọc và script smoke HTTPS không gọi AI/gửi thư.
- Bổ sung bài test API xuyên suốt và ma trận quyền; sửa một test prompt còn lấy khóa
  MySQL thật trong bộ test giả lập.

## Kết quả tự động

| Hạng mục | Kết quả |
| --- | --- |
| Pytest trên môi trường Python của dự án | 220 passed |
| Pytest trong image Linux API, `--network none` | 220 passed |
| Playwright auth/chat/candidates/interviews/emails/ingestion/admin/Ops + release checks | 57 passed |
| ESLint và TypeScript | Pass |
| Production image frontend standalone | Build thành công |
| Production image API/worker (PyTorch CPU) | Build thành công |
| Compose config | Valid |

Các ca backend dùng database tạm, storage/vector/broker/provider/Gmail giả lập.
Bài kiểm tra tích hợp dùng parser PDF, chunking, transaction SQL, LangGraph
interrupt/resume, xác nhận gửi và lịch sử thật trong cùng test; external I/O được
thay bằng fake. Playwright dùng Next/BFF thật và backend giả lập.

## Kiểm tra Docker/HTTPS/MySQL thực

Đã build/chạy project kiểm tra riêng `cv-rag-verify`, database/volume mới và dữ liệu
giả. API key provider để trống, Beat không chạy; proxy chỉ bind localhost.

- `prepare` chạy toàn bộ migration lên `0015` trên MySQL mới và chuẩn bị storage/vector.
- API và frontend healthy; worker Celery trả lời ping.
- Đăng nhập đi qua Caddy HTTPS → Next BFF → FastAPI → MySQL.
- Certificate localhost được xác minh bằng CA của stack, không tắt kiểm tra TLS.
- Cookie `__Host-cv_session` có Secure/HttpOnly/SameSite=Lax; bearer token không có
  trong JSON login.
- Đọc ứng viên/hội thoại có `no-store`; mutation thiếu Origin bị chặn.
- Admin đọc được các API quản trị; logout thu hồi phiên.
- Hai tester với hai phòng ban và CV giả: mỗi người chỉ thấy CV của phòng mình,
  URL chi tiết/ảnh phòng kia trả 404, API email trả 403.
- Hội thoại tạo riêng: người kia đọc trả 404; xóa hội thoại của mình và logout thành công.

Container/network/volume và thông tin đăng nhập tạm của project kiểm tra đã được
dọn sau khi chạy. Hai image demo vẫn có sẵn trên máy; môi trường phát triển hiện có
được giữ nguyên.

Sau khi gộp Compose, đã kiểm tra thêm project `cv-rag-merge-check`: mặc định chỉ có
5 dịch vụ dữ liệu/khởi tạo, profile demo thêm ứng dụng và scheduler chỉ thêm Beat.
Stack đã gộp khởi động thành công; migration/storage/vector/worker và smoke HTTPS
đăng nhập/quyền/Origin/logout đều pass. Project kiểm tra dùng tên container và
volume tạm riêng; tài liệu vận hành chỉ còn một `docker-compose.yml`.

## Những gì chưa được suy ra từ kiểm thử này

Chưa gọi Gemini, tải prompt bằng credentials demo hoặc gửi Gmail thật trong đợt
kiểm tra. Chưa nghiệm thu chất lượng extraction/ranking trên bộ CV có đáp án chuẩn,
quota provider, OAuth refresh và việc thư đến mailbox thực. Các bước này có trong
[checklist nghiệm thu](release-checklist.md). Không có domain public được triển khai.

Requirements Python còn các khoảng version và một số service tag có thể thay đổi;
cần pin image/digest sau khi nghiệm thu một bản demo và chạy lại test khi rebuild.

## Môi trường phát triển hiện có

Kiểm tra chỉ đọc cho thấy API/frontend, Redis, Qdrant và MinIO truy cập được;
collection khớp embedding dimension, cấu hình Gemini/LangSmith có mặt. LangSmith
dùng tên biến thay thế `LANGCHAIN_API_KEY`, được hỗ trợ trong script readiness.

Database môi trường này đang ở `0014` trong khi source yêu cầu `0015`. Worker hiện
tại chưa trả lời ping. Không chạy migration hoặc thay dữ liệu ứng dụng hiện có trong
lần kiểm chứng này; thực hiện các lệnh ở [hướng dẫn demo](../deployment/demo.md)
khi dùng lại môi trường phát triển. OAuth hiện có không được đọc/xác thực trong đợt này.
