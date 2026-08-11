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

CV:
---
{text}
---"""
