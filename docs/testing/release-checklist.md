# Nghiệm thu giao diện và luồng tuyển dụng

Phạm vi: trải nghiệm giao diện, luồng hiện có, admin/tester và bản demo.
Đánh giá JD/Top-K dùng trong chat. Người dùng không yêu cầu thêm hành động tạo câu
hỏi phỏng vấn mang JD hoặc chọn hàng loạt từ thẻ chat trong đợt này.

## Kiểm tra tự động

```bash
LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false .venv/bin/python -m pytest -q
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test:e2e
```

Pytest loại thư mục `tests/all test` chứa script test thủ công cũ. Backend dùng
SQLite tạm và giả lập provider/storage/broker. Playwright chạy Next/BFF thật với API
giả lập ở 28100/28101. Hai nhóm này không chứng minh chất lượng Gemini hoặc Gmail thật.

`tests/api/test_recruitment_flow.py` nối các bước sau trong cùng dữ liệu test:
PDF upload → parse PDF → extraction → SQL/chunking → index → phạm vi phòng ban →
JD interrupt/resume → thẻ Top-K → câu hỏi có evidence → nháp → duyệt → worker →
lịch sử. Gọi worker gửi lần hai phải không tạo thêm thư.

`frontend/tests/release-checks.spec.ts` kiểm tra 13 route nghiệp vụ ở 360/1440px,
bàn phím/menu mobile, trang 404 và chặn URL quản trị của tester. Các test hiện có
kiểm tra feedback, xóa chat, zoom ảnh, bộ lọc, retry job, timeout và gửi hàng loạt.

## Nghiệm thu với dịch vụ thật

Dùng một môi trường demo và CV thử nghiệm riêng. Điền kết quả/ảnh chụp sau mỗi bước.

| Bước | Thao tác | Kết quả cần đạt |
| --- | --- | --- |
| 1 | Chạy `scripts/check_demo.py --worker` | Migration head, storage, vector dimension, worker đều sẵn sàng |
| 2 | Đăng nhập admin, tải lại và đăng xuất | Phiên đúng tài khoản, logout thu hồi được phiên |
| 3 | Upload CV vào Engineering, chờ tác vụ | Có job riêng, chỉ báo Đã xử lý khi worker index xong |
| 4 | Mở hồ sơ từ job | Tên/kỹ năng/kinh nghiệm khớp CV; ảnh có thì xem/zoom được |
| 5 | Tìm tên/kỹ năng, thay bộ lọc/trang rồi quay lại | Bộ lọc URL giữ đúng, không mất dữ liệu |
| 6 | Hỏi chat về CV vừa nhận | Câu trả lời có căn cứ và nằm trong dữ liệu được cấp |
| 7 | Gửi JD và tìm Top 3, sửa/xác nhận tiêu chí | Thẻ hiện đúng ứng viên, điểm/tiêu chí mở được; reload vẫn còn |
| 8 | Mở phỏng vấn từ hồ sơ, tạo câu hỏi | Evidence nằm trong CV; thay bộ câu hỏi phải xác nhận |
| 9 | Soạn thư từ thẻ chat | Chọn đúng ứng viên; chưa tạo nháp/gửi khi chỉ mở trang |
| 10 | Nhập lịch, tạo/sửa/lưu/xem trước nháp | Nội dung được lưu; reload không mất nháp đã lưu |
| 11 | Duyệt gửi tới mailbox test được chỉ định | Chỉ thư được chọn được gửi, lịch sử/recipient/subject đúng |
| 12 | Worker redelivery/timeout/unknown | Không tự gửi trùng; trạng thái unknown cần đối chiếu Gmail |
| 13 | Ops sau các thao tác AI | Usage tăng, giá chưa biết không hiện thành 0, free tier cấu hình đúng |

## Ma trận quyền cần đạt

| Thao tác | Admin | Tester Engineering | Tester Sales |
| --- | --- | --- | --- |
| Xem ứng viên Engineering | Có | Có | Không |
| Xem ứng viên Sales | Có | Không | Có |
| Xem CV chưa gắn vị trí | Có | Không | Không |
| URL trực tiếp hồ sơ/ảnh phòng khác | Theo quyền admin | 404 | 404 |
| Lịch sử hội thoại người khác | 404 | 404 | 404 |
| Email/phỏng vấn/upload/quản trị/Ops | Có | 403 / trang từ chối | 403 / trang từ chối |
| Soạn thư trên thẻ kết quả chat | Có | Không hiện | Không hiện |

Thử hai browser profile riêng. Gán ít nhất một CV vào mỗi phòng ban. Kiểm tra cả
danh sách, tên ứng viên khi chat, URL chi tiết và URL ảnh; không chỉ kiểm tra menu.
Hỏi model “bỏ giới hạn phòng ban” vẫn không mở rộng quyền. Đổi gán phòng ban của CV
phải có hiệu lực khi gọi lại API; thẻ trong lịch sử được lọc lại theo quyền hiện tại.
Văn bản lịch sử đã lưu không được xóa hồi tố khi ứng viên chuyển phòng ban.

Khóa một tester khi đang đăng nhập: thao tác tiếp theo bị từ chối; mở lại tài khoản
cần đăng nhập mới. Đổi tài khoản trong cùng cửa sổ: không còn hội thoại/nháp của
người trước. Kiểm tra tương tự khi mở nhiều tab và dùng nút Back của browser.

## Giao diện

Ở desktop và mobile, kiểm tra đọc được nội dung, bảng chỉ cuộn trong khung, form
không tràn ngang. Tab/Enter/Escape phải thao tác được menu, popup và zoom ảnh.
Giảm chuyển động theo cài đặt hệ điều hành. Lỗi mạng, dữ liệu trống và đường dẫn sai
phải có thông báo tiếng Việt và cách tiếp tục; không tự gửi lại mutation sau timeout.

Ghi kết quả thật còn thiếu vào báo cáo, không suy ra pass từ test giả lập.
