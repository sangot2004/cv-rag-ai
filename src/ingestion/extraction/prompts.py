CLASSIFY_CV_PROMPT = """Xác định văn bản sau có phải là CV/Resume ứng tuyển việc làm không.
Chỉ trả is_cv=true khi văn bản thực sự chứa thông tin cá nhân, kinh nghiệm làm việc, hoặc học vấn
của một người đang ứng tuyển. Các loại văn bản khác (hợp đồng, hóa đơn, thư thông báo...) phải
trả is_cv=false.

Văn bản (có thể bị cắt bớt nếu quá dài):
---
{text}
---"""


EXTRACT_CV_PROMPT = EXTRACT_CV_PROMPT = """Trích xuất thông tin từ CV sau thành dữ liệu có cấu trúc.

NGUYÊN TẮC CHUNG:
- Chỉ trích xuất thông tin có bằng chứng rõ ràng trong CV.
- Không tự bổ sung thông tin từ kiến thức bên ngoài.
- Trường tùy chọn không xuất hiện hoặc không xác định được: để None.
- Danh sách không có thông tin được xác nhận: để rỗng.
- Văn bản CV có thể bị đảo thứ tự do quá trình extract/OCR.
  Không suy đoán quan hệ giữa các mục chỉ dựa vào vị trí dòng.

VỀ NỘI DUNG MẪU VÀ PLACEHOLDER:
- Không coi nội dung trong "[e.g., ...]", "[Technologies Used, e.g., ...]",
  "[Your Name]" hoặc các hướng dẫn điền mẫu tương tự là thông tin thật.
- Dấu ngoặc vuông thông thường không tự động có nghĩa là placeholder.
  Ví dụ "[React / HTML / Tailwind CSS]" không chứa hướng dẫn điền mẫu
  vẫn có thể là danh sách công nghệ được xác nhận.
- Một công nghệ xuất hiện trong placeholder vẫn được trích xuất nếu
  được xác nhận độc lập ở phần khác của CV.

VỀ SKILLS:
- Chỉ lấy kỹ năng được ghi rõ hoặc được xác nhận qua mô tả công việc,
  dự án hay chứng chỉ.
- Không lấy kỹ năng chỉ xuất hiện trong nội dung mẫu.
- Tách từng kỹ năng thành một phần tử trong danh sách.
- Loại bỏ kỹ năng trùng lặp.
- Không suy diễn thêm kỹ năng từ chức danh hoặc ngành học.

VỀ EXPERIENCE VÀ NGÀY THÁNG:
- Chỉ gán công ty, chức danh và ngày tháng khi xác định rõ chúng thuộc
  cùng một công việc.
- Không gán các mốc thời gian rời rạc dựa vào thứ tự văn bản extract.
- Nếu không xác định được ngày thuộc công việc nào, để ngày đó là None.
- Chuẩn hóa ngày tháng về YYYY-MM khi xác định được cả năm và tháng.
- Nếu chỉ có năm, không tự chọn tháng; để trường ngày là None.
- Nếu CV ghi "Present", "Hiện tại" hoặc "Now", để end_date=None.
- Nếu không ghi ngày kết thúc, cũng để end_date=None; điều này không
  tự động chứng minh công việc vẫn đang tiếp diễn.
- Không tự bịa tên công ty. Nếu thiếu thông tin bắt buộc để tạo một
  mục experience hợp lệ, không tạo mục đó bằng giá trị suy đoán.

VỀ TOTAL_YEARS_EXPERIENCE:
- Chỉ tính khi các mục kinh nghiệm có đủ ngày bắt đầu và kết thúc,
  đồng thời xác định rõ ngày thuộc công việc tương ứng.
- Nếu ngày tháng thiếu, mơ hồ hoặc công việc đang tiếp diễn nhưng
  không có mốc tính được cung cấp rõ ràng, để None.
- Không tự suy đoán ngày hiện tại.
- Không dùng thời gian học hoặc làm dự án cá nhân thay cho kinh nghiệm
  làm việc.
- Không cộng trùng các khoảng thời gian làm việc chồng lấn.
- Khi đủ dữ liệu, tính tổng thời gian làm việc và làm tròn 1 chữ số
  thập phân.

VỀ EDUCATION:
- Chỉ lấy trường, bằng cấp, chuyên ngành và năm tốt nghiệp được ghi rõ.
- Không suy đoán năm tốt nghiệp từ tuổi hoặc khoảng thời gian khác.
- Không tự bổ sung bằng cấp dựa vào tên trường.

VỀ CERTIFICATES:
- Chỉ lấy các mục được ghi rõ là chứng chỉ hoặc kết quả chứng nhận,
  trong phần "Chứng chỉ"/"Certifications"/"Certificates" hoặc phần
  khác có bằng chứng rõ ràng.
- Không tự suy diễn một khóa học hay dự án thành chứng chỉ đã được cấp.
- Giữ điểm số nếu có, ví dụ "IELTS 7.0", "TOEIC 900".
- issuer, issue_date và credential_id để None nếu không được ghi rõ.
- Để danh sách rỗng nếu không có chứng chỉ được xác nhận.

VỀ PROJECTS:
- Lấy từ phần "Dự án"/"Projects"/"Personal Projects" nếu có.
- Tách rõ:
  + role: vai trò của ứng viên, chỉ lấy nếu CV ghi rõ.
  + tech_stack: danh sách công nghệ được xác nhận trong dự án.
  + description: nội dung, mục tiêu hoặc đóng góp được ghi trong CV.
- Không lấy công nghệ chỉ nằm trong placeholder làm tech_stack.
- Không bổ sung công nghệ dựa vào tên hoặc loại dự án.
- Không lặp lại role hay danh sách tech_stack trong description nếu
  không cần thiết.
- Nếu dự án chỉ là một dòng trong Experience và không có mục Projects
  riêng, giữ trong mô tả kinh nghiệm, không tạo thêm project trùng lặp.
- Không tự bổ sung ngày bắt đầu hoặc kết thúc dự án.

VỀ DESCRIPTION:
- Giữ sát nội dung CV, có thể nối các dòng bị ngắt thành câu dễ đọc.
- Không thêm thành tích, số liệu, trách nhiệm hoặc công nghệ không có
  trong CV.
- Không phóng đại mức độ đóng góp của ứng viên.

CV:
---
{text}
---"""


OCR_CV_IMAGE_PROMPT = """Đây là ảnh chụp/scan 1 hoặc nhiều trang CV (resume).
Đọc và chép lại TOÀN BỘ text xuất hiện trong ảnh theo đúng thứ tự, giữ
nguyên cấu trúc dòng/đoạn/mục càng sát bản gốc càng tốt (tên, thông tin
liên hệ, kinh nghiệm, học vấn, kỹ năng, chứng chỉ, dự án...).

Chỉ trả về text đã đọc được, KHÔNG thêm bình luận, giải thích, hay tóm tắt.
Nếu có nhiều ảnh (nhiều trang), nối text các trang lại theo đúng thứ tự."""


EXTRACT_JD_PROMPT = """Trích xuất thông tin từ Job Description (JD) sau thành
dữ liệu có cấu trúc. Nếu JD không ghi rõ 1 trường, để None thay vì tự bịa ra
(ví dụ JD không nói rõ số năm kinh nghiệm thì min_years_experience=None).

required_skills: chỉ liệt kê kỹ năng/công nghệ CỤ THỂ được đề cập là bắt
buộc hoặc quan trọng, không liệt kê các câu mô tả chung chung ("có tinh
thần trách nhiệm", "làm việc nhóm tốt").

JD:
---
{text}
---"""
