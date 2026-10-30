# Thẻ đánh giá và Top-K trong chat

Kết quả mới từ `find_top_candidates_for_jd` và `evaluate_candidate_against_jd`
được hiển thị trong câu trả lời, cùng với phần văn bản của trợ lý.

- Tên ứng viên, vị trí và liên kết hồ sơ lấy từ SQL theo quyền hiện tại.
- Điểm tổng, tiêu chí, lý do, điểm mạnh/cần làm rõ lấy từ kết quả evaluator.
- Điểm là thang 1–5; không chuyển thành xác suất tuyển dụng hoặc phần trăm phù hợp.
- Lý do chấm điểm là nhận xét của AI. Chưa có trích dẫn nguồn được kiểm chứng riêng
  cho từng tiêu chí; FE không đặt nhãn “bằng chứng đã xác minh”.
- Thẻ có nút Xem hồ sơ và phần chi tiết tiêu chí đóng/mở, bố cục hỗ trợ mobile.
- Admin có thêm nút **Soạn thư mời** trên mỗi thẻ (cả Top-K và đánh giá JD).
  Liên kết mở `/emails/compose?candidate=<candidate_id>` để tải và chọn sẵn đúng
  ứng viên từ API hồ sơ. Tester không thấy nút này; trang soạn thư và API email
  tiếp tục kiểm tra quyền admin.
- Mở trang soạn thư chưa tạo nháp, gọi AI hay gửi email. Admin nhập thông tin
  phỏng vấn rồi bấm **Tạo bản nháp** để tiếp tục luồng xem, sửa và duyệt thư hiện có.

## Contract

`Message` trong response answer và history có thêm `candidate_results`, mặc định `[]`.
Mỗi nhóm có `kind` (`candidate_ranking` hoặc `candidate_evaluation`), `title`,
`unavailable` và `items`. Mỗi item gồm candidate_id, full_name, applied_position,
rank, overall_score, summary, strengths, concerns và criteria.

Backend tạo artifact riêng trên ToolMessage (`content_and_artifact`) và lưu cùng
checkpoint. Chỉ artifact của hai tool hợp lệ, khớp tool_call_id của AIMessage trước
đó, được đọc. Không phân tích JSON/UUID từ lời văn của AI để tạo thẻ. Artifact sai
schema bị bỏ qua; văn bản cũ vẫn đọc bình thường. Không gửi artifact thô cho FE.

Projection gắn các nhóm vào câu trả lời cuối sau tool, xóa bộ đệm khi sang câu hỏi
mới; hỗ trợ nhiều tool calls trong cùng lượt. Adapter kiểm tra lại phạm vi SQL khi
đọc lịch sử: CV chuyển phòng ban/đã xóa bị loại khỏi thẻ, có thông báo chung và
không trả tên/ID/điểm của các item đó. Endpoint hồ sơ/ảnh tiếp tục tự kiểm tra quyền.
Văn bản hội thoại đã lưu giữ nguyên nội dung lịch sử; việc lọc thẻ không xóa hồi tố
những thông tin đã từng được gửi trong câu trả lời văn bản.

## Chạy thử

1. Reload/restart FastAPI và frontend. Không có migration hay dependency mới.
2. Trong chat, gửi JD và yêu cầu tìm Top 3 ứng viên.
3. Xác nhận tiêu chí rồi chờ xếp hạng.
4. Kiểm tra thẻ, mở chi tiết tiêu chí, bấm Xem hồ sơ.
5. Tải lại hội thoại: thẻ vẫn hiện cùng câu trả lời.
6. Thử với tester để kiểm tra phạm vi phòng ban.
7. Với admin, bấm **Soạn thư mời** trên thẻ: kiểm tra tên ứng viên được chọn sẵn,
   vị trí mặc định lấy từ hồ sơ và có thể sửa. Nhập thông tin phỏng vấn rồi tạo nháp.
8. Với tester, kiểm tra không có nút soạn thư trên thẻ và không truy cập được trang email.

Hội thoại cũ không có artifact vẫn hiển thị văn bản, không tự gọi lại AI để dựng thẻ.
Kiểm thử tự động dùng model/mock ngoại tuyến; chưa chạy ranking mới bằng Gemini thật
trong lần triển khai này.
