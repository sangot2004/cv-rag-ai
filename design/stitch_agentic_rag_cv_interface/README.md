# Review thiết kế F1 — CV RAG AI

Cập nhật 19/10/2026. Mở **index.html** để xem danh mục, chọn vai trò và chọn trạng thái.

## Chạy preview

Đứng ở thư mục gốc repository:

```bash
.venv/bin/python -m http.server 8765 --bind 127.0.0.1 --directory design/stitch_agentic_rag_cv_interface
```

Mở **http://127.0.0.1:8765/**. Khi xong, Ctrl+C ở terminal chạy server.
Có thể đọc HTML trực tiếp, nhưng HTTP localhost thuận tiện cho clipboard và kiểm tra trình duyệt.

## Phạm vi đã chỉnh

- Login: username/password, show/hide, lỗi đăng nhập, backend unavailable, hết phiên, logout.
- Workspace/chat: lịch sử có chọn/xóa, scope theo role, role admin/tester nhất quán.
- JD: nhiều confirmation, validation đúng schema, partial edits, 0/null, giữ draft card còn lại.
- Error/recovery: running, loading, failed/interrupted, timeout, 404, stale, cleanup pending.
- Mobile: drawer có focus/Escape/backdrop; composer nằm trong layout, không phủ lên form.
- `cognitive_talent_system/DESIGN.md`: token thống nhất và quy tắc bàn giao F1.

Màu xanh/lavender và hướng bố cục được giữ từ Stitch. Các màn ngoài F1 ở mục cuối
của gallery là bản tham khảo gốc, chưa được chuẩn hóa hoặc kết nối backend.

## Cách thử tương tác

1. Chọn Admin/Tester trên gallery rồi mở màn tương ứng.
2. Login: dùng username và password giả bất kỳ không rỗng. Username bắt đầu bằng
   `tester` mở vai trò tester; các trường hợp khác theo role đang chọn. Đây không
   phải kiểm tra mật khẩu/quyền thật. Password không được ghi vào URL hoặc storage.
3. Chat trống: bấm gợi ý, sửa câu hỏi và gửi. Câu chứa JD sẽ mô phỏng card xác nhận.
4. Pending: thay số năm bằng 0, để trống học vấn, chỉnh Top-K; thêm/xóa kỹ năng.
5. Multiple: sửa card thứ hai rồi hủy card thứ nhất; draft card thứ hai phải còn.
6. Stale: chỉ tải lại tiêu chí; form cũ không được dùng để gửi xác nhận.
7. Timeout: bấm kiểm tra trạng thái → running → kiểm tra tiếp → answer, không resend câu hỏi.
8. Delete: mở dialog, giữ lại/xóa; cleanup pending có đường thử lại riêng.
9. Thu nhỏ dưới 768px: mở drawer, chọn hội thoại, Escape để đóng và trả focus.
10. Logout: về trang login, không mang theo lịch sử hoặc password.

## Giới hạn của prototype

- Không gọi FastAPI, Gemini, gửi email hoặc thay dữ liệu dự án.
- Tương tác, câu trả lời và thời gian chờ là mô phỏng cố định; không phải phép đo latency.
- Role/state trên URL chỉ phục vụ duyệt thiết kế, không có tác dụng phân quyền thật.
- Messages/draft trong bộ nhớ; reload quay về dữ liệu mẫu theo state URL. Không có
  auth cookie thật, không chứng minh khôi phục session hoặc checkpoint sau reload.
- Chưa có Next.js/BFF, cookie HttpOnly/CSRF hay tích hợp API. Các phần đó theo
  [kế hoạch FE](../../docs/frontend/FE_IMPLEMENTATION_PLAN.md).
- Preview giữ vote đã gửi trong lượt đang mở; backend thật đang append và chưa có API đọc/upsert vote.

## File chính

| File | Vai trò |
| --- | --- |
| `index.html` | Gallery và links tới các trạng thái |
| `shared/f1.css` | Token, layout, responsive và component dùng chung |
| `shared/f1.js` | Dữ liệu mẫu, tương tác và state preview |
| `auth_01_ng_nh_p_h_th_ng/code.html` | Màn login |
| `chat_02_kh_ng_gian_h_i_tho_i_x_c_nh_n_jd/code.html` | Workspace/chat |
| `sys_01_kh_ng_quy_n_truy_c_p_403/code.html` | Màn không đủ quyền |
| `previews/` | Ảnh review từ trình duyệt |
| `cognitive_talent_system/DESIGN.md` | Quy tắc thiết kế mới |

`fe_implementation_plan.md` trong bộ export là bản sao kế hoạch lúc gửi Stitch.
Bản kế hoạch chính để tiếp tục cập nhật nằm ở `docs/frontend/FE_IMPLEMENTATION_PLAN.md`
trong repository; không dùng các relative link của bản sao như tài liệu chính.

## Khi chuyển sang Next.js

Tách thành AppShell, ConversationList, MessageList, ChatComposer, CriteriaForm,
ErrorPanel, ConfirmDialog và AuthForm. Loại bỏ dữ liệu mẫu và timer mô phỏng;
state lấy từ response/history thật, identity lấy từ session backend. Không đưa
bộ chọn role/state của gallery hoặc inspection hook `CVRagPreview` vào sản phẩm.

Các mục admin disabled chỉ để review bố cục tương lai; bản phát hành F1 ẩn chúng
cho đến khi có API/màn tương ứng. Hành vi về resume, lỗi, cleanup và feedback phải
khớp [contract hiện tại](../../docs/api/contract.md).

## Kiểm chứng bản review 19/10/2026

Đã kiểm tra bằng Chrome headless ở chiều rộng 1440, 768, 390 và 320 px, cả hai
vai trò, các trạng thái trong gallery; không phát hiện page overflow hoặc lỗi
JavaScript trong các trường hợp đã chạy. Kiểm tra tương tác đạt cho login/logout,
0/null và partial edits, nhiều confirmation, stale, feedback, xóa/cleanup,
recovery theo trạng thái và drawer keyboard/focus. Các kiểm tra này chỉ xác minh
prototype; chưa thay thế E2E sau khi nối FastAPI và BFF.

Ảnh review bổ sung nằm trong `previews/`. Các `screen.png` của login/chat/403 đã
được chụp lại; các ảnh Stitch khác vẫn là bản tham khảo ban đầu.
