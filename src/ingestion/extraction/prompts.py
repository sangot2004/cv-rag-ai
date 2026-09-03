CLASSIFY_CV_PROMPT = """Xác định văn bản sau có phải là CV/Resume ứng tuyển việc làm không.
Chỉ trả is_cv=true khi văn bản thực sự chứa thông tin cá nhân, kinh nghiệm làm việc, hoặc học vấn
của một người đang ứng tuyển. Các loại văn bản khác (hợp đồng, hóa đơn, thư thông báo...) phải
trả is_cv=false.

Văn bản (có thể bị cắt bớt nếu quá dài):
---
{text}
---"""


EXTRACT_CV_PROMPT = """Trích xuất thông tin từ CV sau thành dữ liệu có cấu trúc.
Nếu một trường không xuất hiện rõ ràng trong CV, để None thay vì tự bịa ra.
Tính total_years_experience bằng cách cộng khoảng thời gian của các mục experience,
làm tròn 1 chữ số thập phân.

QUAN TRỌNG về end_date: nếu CV ghi "Present", "Hiện tại", "Now", hoặc không ghi ngày
kết thúc (nghĩa là công việc/học vấn đó vẫn đang tiếp diễn), PHẢI để end_date=None.
TUYỆT ĐỐI không tự suy đoán hay bịa ra một ngày cụ thể cho trường hợp này.

Về certificates: chỉ lấy các mục CV ghi rõ trong phần "Chứng chỉ"/"Certifications"/
"Certificates" — KHÔNG tự suy diễn 1 khóa học hay 1 dự án thành chứng chỉ nếu CV
không ghi rõ đó là chứng chỉ đã được cấp. Để rỗng nếu CV không có phần này.

Về projects: lấy từ phần "Dự án"/"Projects" nếu có. Tách rõ 3 phần riêng biệt:
- role: vai trò của ứng viên trong dự án (nếu CV ghi rõ)
- tech_stack: danh sách công nghệ dùng trong dự án (tách thành list, không để chung câu văn)
- description: chỉ mô tả nội dung/mục tiêu dự án, KHÔNG lặp lại role hay tech_stack đã tách
Nếu 1 dự án chỉ là 1 dòng liệt kê trong phần Experience (không có mục Projects riêng),
không cần tách ra thành project — chỉ lấy phần Projects là mục riêng biệt trong CV.

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
