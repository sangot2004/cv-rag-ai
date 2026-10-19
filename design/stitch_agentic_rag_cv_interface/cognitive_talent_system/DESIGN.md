---
name: Cognitive Talent System
product: CV RAG AI
revision: F1-review-2026-10-19
status: interactive-design-prototype
colors:
  primary: '#00288e'
  primary-hover: '#1e40af'
  primary-soft: '#eaf0ff'
  canvas: '#faf8ff'
  surface: '#ffffff'
  surface-low: '#f2f3ff'
  text: '#131b2e'
  muted: '#505f76'
  border: '#dce2f0'
  outline: '#757684'
  amber: '#92400e'
  amber-bg: '#fff8e8'
  amber-border: '#f5d58a'
  error: '#ba1a1a'
  error-bg: '#fff1f0'
  success: '#006b4f'
  success-bg: '#eaf8f2'
typography:
  heading:
    fontFamily: Plus Jakarta Sans, Inter, system-ui, sans-serif
    desktop: 27px–34px
    mobile: 25px–27px
  body:
    fontFamily: Inter, system-ui, sans-serif
    fontSize: 15px
    lineHeight: 1.6
  message:
    fontSize: 14px
    lineHeight: 1.85
  label:
    fontSize: 13px
    fontWeight: 600
  metadata:
    fontSize: 11px–12px
  mobile-composer:
    fontSize: 16px
rounded:
  input: 8px
  button: 8px
  card: 12px
  login-card: 16px
spacing:
  step: 4px
  sidebar-desktop: 272px
  sidebar-tablet: 250px
  content-gutter-desktop: 30px
  content-gutter-mobile: 14px
  chat-reading-width: 840px
breakpoints:
  desktop: 1101px and above
  tablet: 768px–1100px
  mobile: below 768px
---

# CV RAG AI — Quy tắc thiết kế và bàn giao

**Cập nhật:** 19/10/2026. Bản này chuẩn hóa thiết kế **F1: đăng nhập, workspace,
chat, JD confirmation và lỗi quyền** từ bộ Stitch gốc.

- Mở `../index.html` để chọn vai trò và xem từng trạng thái.
- `../shared/f1.css` triển khai token và layout chung.
- `../shared/f1.js` chỉ mô phỏng tương tác bằng dữ liệu giả trong bộ nhớ.
- Chi tiết cách chạy và giới hạn ở `../README.md`.
- Kế hoạch tổng thể: `../../../docs/frontend/FE_IMPLEMENTATION_PLAN.md`.

Các màn ứng viên, email, Ops và quản trị trong bộ export vẫn là thiết kế tham khảo
cho đợt sau. Những field/thống kê trên các màn đó chưa được coi là contract đã có.

## 1. Hướng hình ảnh

Giữ hướng enterprise gọn, sáng và ưu tiên đọc nội dung: nền lavender rất nhạt,
sidebar trắng, màu xanh đậm cho hành động chính, amber cho JD chờ xác nhận.
Không đưa nhãn phát triển như F1/F2/CAND-02 vào màn làm việc của người dùng.

Tên sản phẩm hiển thị là **CV RAG AI**, mô tả ngắn “Trợ lý tuyển dụng”. Dùng dấu
hiệu logo tài liệu đơn giản bằng SVG, không phụ thuộc ảnh avatar/logo giả từ URL
Stitch bên ngoài. Avatar phiên làm việc dùng chữ đầu từ username.

## 2. Token và khả năng đọc

Bảng YAML ở đầu file là bộ token F1. Không dùng một bảng màu khác trong mô tả
hoặc ghi đè cùng tên token theo từng màn.

- Primary: `#00288e`; hover: `#1e40af`; chữ trên primary: trắng.
- Nền: `#faf8ff`; surface: trắng; nội dung: `#131b2e`; phụ/placeholder: `#505f76`.
- Pending: chữ `#92400e`, nền `#fff8e8`, border `#f5d58a`.
- Error: `#ba1a1a`, nền `#fff1f0`; success: `#006b4f`, nền `#eaf8f2`.
- Màu pending không có nghĩa là đã trích xuất chính xác; người dùng vẫn phải kiểm tra.
- Badge có text kèm ý nghĩa, không chỉ dựa vào chấm màu.

Preview dùng font hệ thống làm fallback nếu Inter/Plus Jakarta Sans chưa có trên
máy; không tải font từ CDN. Khi chuyển sang Next.js, cấu hình font đóng gói riêng
và kiểm tra dấu tiếng Việt. Chữ code chỉ dành cho ID kỹ thuật khi cần hỗ trợ,
không dùng font monospace cho toàn bộ kỹ năng hoặc nội dung CV dài.

## 3. Layout và navigation F1

### Desktop/tablet

Workspace gồm sidebar và panel chat. Sidebar chứa:

1. Logo, nút tạo cuộc trò chuyện mới.
2. Danh sách hội thoại gần đây có tiêu đề, trạng thái và nút xóa riêng.
3. Tìm kiếm chỉ trong danh sách đã tải, tối đa 50 theo API hiện tại.
4. Username, role, mô tả phạm vi dữ liệu, đăng xuất.

Panel chat dùng ba hàng layout: header, vùng nội dung cuộn và composer. Composer
không dùng `position: fixed` phủ lên nội dung. Card JD và hàng nút xác nhận phải
cuộn được hoàn toàn vào vùng nhìn thấy.

Khi đang chờ JD, đang xử lý hoặc cần recovery, composer thu gọn thành hướng dẫn
trạng thái thay vì chiếm một ô nhập bị vô hiệu hóa lớn ở cuối màn.

### Mobile

- Dưới 768px, sidebar trở thành drawer; không giữ padding trái 260px cố định.
- Có backdrop, nút đóng, Escape, focus trap và trả focus về đúng vị trí.
- Nội dung chính inert khi drawer mở; drawer inert khi đóng.
- Form/card xếp phù hợp ở 390px và 320px; nút confirmation full width.
- Header và composer là các hàng riêng, vùng messages cuộn độc lập.
- Ô nhập chat 16px để tránh phóng to bất ngờ trên một số trình duyệt điện thoại.

### Vai trò

F1 hiện có cùng nghiệp vụ chat cho cả admin và tester. Mỗi người chỉ có hội thoại
của mình; admin không được xem hội thoại tester.

- Tester: ẩn toàn bộ nhóm quản trị, giữ mô tả “CV thuộc phòng ban được cấp”.
- Admin: trong prototype có nhóm “Quản trị / Sắp ra mắt” với nút disabled để xem
  hướng mở rộng. Bản phát hành F1 sẽ ẩn nhóm này cho đến khi API/màn sẵn sàng.
- Không giả định `/auth/me` đã có full name, avatar hoặc department name; API hiện
  chỉ trả username, role, user ID và department ID.
- Bản 403 phải hiển thị cùng identity với sidebar, không ghép Tester ở nội dung
  với Admin ở footer. Chỉ có lối về chat và đăng nhập tài khoản khác.

Role trong query string ở prototype chỉ chọn cảnh thiết kế, không tạo quyền truy
cập thật. FastAPI vẫn quyết định quyền khi triển khai FE.

## 4. Đăng nhập

- Dùng “Tên đăng nhập” và “Mật khẩu”; giới hạn tương ứng 100 và 256 ký tự.
- Cho phép password manager, paste, Enter submit, hiện/ẩn mật khẩu có nhãn.
- Khóa submit lặp trong lúc chờ. Khi lỗi, hiện thông báo an toàn, không tiết lộ
  username có tồn tại hay không; giữ username và xóa password trong preview.
- Có trạng thái credentials không hợp lệ/tạm khóa, backend không khả dụng, đang
  đăng nhập, phiên hết hạn và đã đăng xuất.
- Quy tắc 12 ký tự là lúc tạo tài khoản, không áp thành lỗi validation mới ở login.
- Không có SSO, TOTP/2FA, tự đăng ký, khôi phục mật khẩu qua email hoặc lựa chọn
  “ghi nhớ” kéo dài phiên khi backend chưa hỗ trợ.

BFF/cookie HttpOnly vẫn là phương án triển khai tiếp theo, chưa tồn tại trong
prototype. Không mô tả việc bấm login ở HTML là đã xác thực với backend thật.

## 5. Hội thoại và dữ liệu hiển thị

- Chat mới chỉ tạo ID khi người dùng chủ động gửi câu đầu/tạo hội thoại qua API,
  không tự tạo bản ghi rỗng sau mỗi reload.
- Bản xem trước dùng câu trả lời text và tên ứng viên giả. Khi nối API, render
  Markdown an toàn từ `message.content`; không thêm HTML/script không tin cậy.
- Dùng message ID từ backend; không tạo timestamp lịch sử giả vì API hiện chưa trả
  timestamp riêng từng message.
- Không hiện nút mở hồ sơ, score card có cấu trúc, xuất report hoặc đính kèm tài
  liệu như một khả năng đã hoạt động khi chưa có API tương ứng.
- Câu hỏi tối đa **20.000 ký tự**; bộ đếm không phải token quota.
- Enter gửi, Shift+Enter xuống dòng, không gửi khi người dùng đang gõ IME.
- Phản hồi 👍/👎 là append theo backend; ghi nhận xong có trạng thái đã lưu trong
  lượt tương tác, không giả lập vote toggle/upsert bền sau reload.
- Draft và dữ liệu của một thread không tràn sang thread khác; đổi user/logout
  xóa state và cache riêng tư khi chuyển sang FE thật.

## 6. Xác nhận JD

Card JD có trạng thái pending màu amber và hai hành động: xác nhận/tìm kiếm,
hủy yêu cầu. Hủy gọi resume với `confirmed: false`, không có nghĩa là dừng graph
đang chạy hoặc xóa hội thoại.

| Trường | Quy tắc |
| --- | --- |
| position_title | Bắt buộc, 1–500 ký tự, không chỉ khoảng trắng |
| required_skills | Tối đa 100 kỹ năng; mỗi tên 1–200 ký tự; thêm/xóa bằng chip |
| min_years_experience | Số không âm hoặc null; giữ đúng 0, không giới hạn tùy tiện 15/30 năm |
| preferred_education | Tối đa 1.000 ký tự hoặc null |
| top_k | Số nguyên từ 1 đến 10 |

- Key của form gồm thread ID và confirmation ID; nhiều interrupt là nhiều card.
- Partial edits chỉ gửi field đã sửa. Không đổi field bỏ qua thành null.
- Để trống số năm/học vấn tương ứng null; số năm bằng 0 vẫn giữ nguyên 0.
- Khi xử lý card thứ nhất, draft đang sửa của card còn lại phải được giữ.
- Pending chặn câu hỏi mới; resume còn pending thì giữ các form chưa xử lý.
- Stale confirmation cần tải lại tiêu chí và đọc lại trước khi xác nhận; không tự
  gửi quyết định cũ vào ID mới.
- Không có trọng số do HR sửa, must-have/nice-to-have riêng hoặc kỹ năng “chắc chắn
  đúng” nếu schema/backend hiện chưa cung cấp các thuộc tính đó.

## 7. Trạng thái lỗi và recovery

| Trạng thái | UI và hành động |
| --- | --- |
| idle | Cho gửi câu hỏi |
| running | Hiện đang xử lý, không gửi lặp; có đường kiểm tra trạng thái |
| awaiting_confirmation | Các card JD và hướng dẫn xác nhận/hủy |
| failed / interrupted | Giữ history đã có, thông báo lượt chưa hoàn tất, tạo chat mới |
| 503 | Dịch vụ tạm không khả dụng; không tự khẳng định hết quota hoặc đếm ngược |
| timeout / mất response | Kiểm tra history; không tự resend POST hoặc khẳng định graph đã dừng |
| stale confirmation | Refetch tiêu chí, không tự áp ID cũ |
| 404 thread | Không tìm thấy hoặc không có quyền; không lộ danh tính người sở hữu khác |
| cleanup pending | Thread đã ẩn nhưng có đường retry DELETE theo ID giữ lại |
| 401 | Xóa dữ liệu phiên phía FE, quay về login với thông báo |
| 403 | Hiện lỗi quyền; không tự logout hoặc gợi ý nâng quyền đã được gửi |

Mã hỗ trợ hiển thị là request ID thật khi tích hợp; preview dùng UUID giả cố định.
Không hiển thị stack trace, credentials hoặc log nội bộ trên giao diện.

Xóa hội thoại có dialog rõ tiêu đề, nút “Giữ lại” và “Xóa hội thoại”. Không hứa mọi
metadata bị xóa vật lý: backend còn tombstone. Nếu cleanup lỗi, vẫn cho chính chủ
thử dọn lại dù hội thoại đã biến mất khỏi sidebar.

## 8. Quy tắc cho các màn sau F1

- Điểm rubric hiện thang 1–5. Nếu chuyển sang 100 cần định nghĩa quy đổi và nhãn;
  không tự gọi điểm đó là xác suất phù hợp, vector similarity hay chất lượng đã kiểm chứng.
- Mail gửi thành công không đồng nghĩa ứng viên đã nhận/mở/đồng ý. Tracking mở thư,
  lịch hẹn, CC/attachment, pause/retry batch cần API/service riêng và chống gửi trùng.
- Ops phân biệt 0 USD, null và thiếu một phần usage. Chỉ hiển thị metric đã đo;
  uptime, RPM/TPM còn lại, TTFT hoặc cache hit rate không được tự tạo.
- Key manager hiện dùng failover; không ghi Round-Robin v2 như tính năng đang có.
- Không thêm cam kết ISO, AES, GDPR/PDPD, log kiểm toán hoặc tự khóa theo ngày
  nếu chưa được xác minh trên hệ thống triển khai.
- Candidate notes, lịch sử report, pipeline tuyển dụng và calendar chỉ mở khi có
  mô hình dữ liệu/contract tương ứng.

## 9. Khả năng truy cập và kiểm tra hình ảnh

- Input có label; lỗi/trạng thái có vùng thông báo; dialog và drawer giữ focus đúng.
- Nút icon có tên truy cập; vùng bấm dễ sử dụng; không ẩn scrollbar toàn hệ thống.
- Tôn trọng reduced-motion; không dùng chuyển động liên tục để minh họa “thông minh”.
- Duyệt trên desktop, tablet, 390px và 320px; vùng chat/composer không tràn ngang.
- Tương phản và keyboard là tiêu chí cần kiểm chứng trên giao diện thực, không
  ghi nhận chứng nhận WCAG chỉ vì đã khai báo trong design system.

Ảnh `screen.png` của ba màn F1 được làm mới từ HTML. Các file trong `../previews/`
minh họa thêm desktop/mobile. Ảnh của các màn ngoài F1 vẫn thuộc bộ export gốc.
