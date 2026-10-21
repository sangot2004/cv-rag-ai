# API ứng viên — F2 bước 1

Danh sách/chi tiết đọc MySQL; endpoint ảnh đọc MinIO. Không gọi model, không cần migration.
Cần `Authorization: Bearer <token>` của admin. Tester nhận `403 FORBIDDEN` kể cả
khi ứng viên thuộc phòng ban của tester; việc tra cứu qua chat vẫn theo quyền hiện có.
Session được kiểm tra lại trên mỗi request. Response thành công có `Cache-Control: private, no-store`.

## Danh sách

`GET /api/candidates`

| Query | Mặc định | Quy tắc |
| --- | --- | --- |
| `page` | 1 | Integer 1–1.000.000 |
| `page_size` | 20 | Integer 1–100 |
| `q` | Không lọc | Tìm một phần tên/email, 1–200 ký tự sau trim |
| `position` | Không lọc | Tìm một phần vị trí ứng tuyển, 1–255 ký tự sau trim |
| `skills` | Không lọc | Lặp query param, tối đa 20 kỹ năng, mỗi kỹ năng 1–100 ký tự |
| `department_id` | Không lọc | UUID; qua job posting của ứng viên |
| `posting_id` | Không lọc | UUID của vị trí tuyển dụng |
| `min_years_experience` | Không lọc | Số hữu hạn, từ 0 trở lên |
| `max_years_experience` | Không lọc | Số hữu hạn, không nhỏ hơn min |
| `sort` | `newest` | `newest`, `oldest`, `name_asc`, `experience_desc` |

Ví dụ:

```text
/api/candidates?page=1&page_size=20&skills=python&skills=sql&min_years_experience=0
```

- Các bộ lọc được kết hợp bằng AND.
- Phải khớp **tất cả** kỹ năng yêu cầu. Mỗi kỹ năng khớp tên chính xác, không phân biệt
  hoa/thường, có dùng bảng alias hiện có (`py` ↔ `python`, `js` ↔ `javascript`, ...).
  `java` không tự khớp `javascript`. Các alias của cùng kỹ năng dùng OR.
- Tên/email/vị trí dùng tìm kiếm chuỗi con; `%` và `_` là ký tự thường, không phải wildcard.
- Bộ lọc kinh nghiệm không tính các hồ sơ có kinh nghiệm null. `0` là giá trị hợp lệ.
- Khi không lọc phòng ban/posting, admin thấy cả hồ sơ chưa gắn posting. Lọc theo
  phòng ban/posting loại các hồ sơ chưa gắn tương ứng. Posting đã ngưng tuyển vẫn
  có thể được xem; trạng thái có trong response.
- Nhiều dòng kỹ năng khớp không làm lặp ứng viên hay tăng `total`.
- Sort có candidate ID làm khóa phụ để các dòng cùng giá trị không nhảy thứ tự.
  `experience_desc` đặt kinh nghiệm null cuối cùng. Đây là phân trang offset;
  dữ liệu mới được thêm giữa các lần đọc có thể làm vị trí trang thay đổi.
- Query không khai báo, chuỗi lọc rỗng, UUID sai, min > max hoặc NaN/Infinity trả 422.

Response:

```json
{
  "items": [{
    "candidate_id": "00000000-0000-4000-8000-000000000001",
    "full_name": "Ứng viên ví dụ",
    "email": null,
    "has_photo": false,
    "applied_position": "Data Engineer",
    "total_years_experience": 0,
    "skills": ["Python", "SQL"],
    "posting": null,
    "created_at": "2026-10-19T00:00:00Z",
    "updated_at": "2026-10-19T00:00:00Z"
  }],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1,
  "has_next": false
}
```

Nếu có posting, trường `posting` chứa `posting_id`, `position_title`, `is_active`
và `department: {department_id, department_name}`.
Danh sách không trả toàn văn CV/phone/storage keys để giữ payload gọn.
Không có kết quả: `items=[]`, `total=0`, `total_pages=0`, `has_next=false`.
Trang vượt quá số trang: `items=[]`, giữ `total` thật và `has_next=false`.

## Chi tiết

`GET /api/candidates/{candidate_id}` — ID phải là UUID.

Trả các trường của một item danh sách cùng:

| Trường | Nội dung |
| --- | --- |
| `phone` | Chuỗi hoặc null |
| `raw_text` | Nội dung CV đã trích xuất hoặc null |
| `experience` | company, title, start_date, end_date, description |
| `education` | school, degree, field, graduation_year |
| `certificates` | name, issuer, issue_date, credential_id |
| `projects` | name, role, tech_stack (array), description, start_date, end_date |

Các danh sách chưa có dữ liệu là `[]`; giá trị chưa biết giữ `null`.
Các mục trong phần hồ sơ giữ thứ tự ID lưu trữ. Kỹ năng được loại trùng chuỗi và sắp tên.
Ngày tháng của kinh nghiệm/chứng chỉ/dự án có dạng `YYYY-MM-DD`, timestamp của hồ sơ dùng UTC.
Không trả hash, object key, thông tin ingestion job hay URL MinIO.
## Ảnh chân dung

`GET /api/candidates/{candidate_id}/photo` — yêu cầu token admin như danh sách/chi tiết.

- Danh sách và chi tiết có thêm `has_photo: boolean`, dựa trên `photo_object_key` đã lưu.
  Không gọi MinIO để kiểm tra từng ảnh khi tải danh sách. Object key và URL MinIO không được trả cho trình duyệt.
- 200 trả trực tiếp ảnh JPEG/PNG/WebP với đúng Content-Type, `Cache-Control: private, no-store`
  và `X-Content-Type-Options: nosniff`. Không tạo bucket khi đọc ảnh.
- 404 `CANDIDATE_PHOTO_NOT_FOUND`: chưa gắn ảnh, object không còn tồn tại hoặc nội dung không phải ảnh được hỗ trợ.
  Hồ sơ không tồn tại vẫn là `CANDIDATE_NOT_FOUND`; MinIO không sẵn sàng trả 503.
- FE tải ảnh qua BFF cùng origin và cookie HttpOnly tại `/api/backend/candidates/{candidate_id}/photo`.
  Ảnh hiển thị dưới email ở bảng ứng viên, rộng 96px/cao tối đa khung 112px, giữ tỷ lệ.
  Không có ảnh hoặc tải ảnh lỗi thì ẩn, danh sách vẫn sử dụng bình thường.
  Trang chi tiết hiển thị ảnh ở đầu hồ sơ (lỗi tải thì dùng avatar chữ cái). Bấm ảnh ở cả hai màn
  để mở hộp thoại xem lớn, zoom 100–300%, cuộn xem, đặt lại và đóng bằng nút/Esc/bấm ngoài.
- `has_photo=true` thể hiện metadata đang có key; ảnh đã mất ở MinIO vẫn có thể trả 404.
  Dùng ảnh đã lưu từ ingestion, không cần extract CV lại. Chưa có endpoint xem/tải PDF.

## Lỗi

| HTTP | Code | Trường hợp |
| --- | --- | --- |
| 401 | AUTHENTICATION_REQUIRED | Thiếu token, hết phiên hoặc tài khoản bị khóa |
| 403 | FORBIDDEN | Đăng nhập tester |
| 404 | CANDIDATE_NOT_FOUND | Admin yêu cầu UUID không tồn tại |
| 404 | CANDIDATE_PHOTO_NOT_FOUND | Không có ảnh chân dung sử dụng được |
| 422 | VALIDATION_ERROR | Query/path không hợp lệ |
| 503 | DEPENDENCY_UNAVAILABLE | Lỗi kết nối/truy vấn database hoặc MinIO |

Giữ error envelope và `X-Request-ID` chung. Không trả SQL/DSN hoặc raw exception.

## Test bằng Swagger

1. Restart Uvicorn, mở `http://127.0.0.1:8000/docs`.
2. Đăng nhập admin qua `/api/auth/login`; dùng token tại nút **Authorize**.
3. Mở nhóm **candidates**, gọi GET danh sách với `page=1`, `page_size=20`.
   Mong đợi 200, có `items` và thông tin phân trang. Nếu DB chưa có ứng viên, danh sách rỗng là hợp lệ.
4. Copy `candidate_id` từ item, gọi GET chi tiết. Mong đợi 200 và các phần hồ sơ tương ứng.
5. Lọc bằng tên/kỹ năng thực tế của hồ sơ. Chọn department/posting ID lấy ngay từ item
   có `posting`; đối chiếu `total` và các dòng trả về. `min_years_experience=0` phải hoạt động.
6. Thử `page_size=101`: 422. Thử UUID ứng viên không tồn tại: 404.
7. Nếu item có `has_photo=true`, gọi GET `/{candidate_id}/photo`: mong đợi ảnh 200 nếu object còn tồn tại. Hồ sơ không có ảnh: 404.
8. Authorize lại bằng token tester, gọi danh sách/chi tiết/ảnh với đầu vào hợp lệ: 403.

Test tự động dùng database SQLite và dữ liệu giả:

```bash
LANGCHAIN_TRACING_V2=false LANGSMITH_TRACING=false OPS_ENABLED=false \
  python -m pytest tests/api/test_candidates.py -q
```

Bao phủ phân trang, trùng kỹ năng/alias, kết hợp bộ lọc, tìm kiếm literal, sort,
zero/null, schema chi tiết, quyền admin/tester, input sai và lỗi database được che thông tin.
