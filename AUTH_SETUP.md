# Đăng nhập và lịch sử chat riêng — CV RAG AI

Gói cập nhật áp dụng lên source ZIP bạn gửi ngày 07/10/2026. Gói chỉ chứa file mới/sửa và hướng dẫn; giải nén rồi chép vào thư mục gốc `cv-rag-ai`, giữ nguyên cấu trúc thư mục. Không thay `.env`, Gmail credentials/token hay database của bạn.

## 1. Hành vi mới

- Chưa đăng nhập: chỉ hiện form đăng nhập.
- Admin: chat riêng, các tab quản trị hiện có, tạo và khóa/mở tài khoản.
- Tester: chat và feedback trên hội thoại riêng; chỉ tra cứu CV thuộc phòng ban được cấp.
- Hai tester trong cùng phòng ban có thể tra cứu cùng tập CV, nhưng không xem lịch sử chat của nhau. Tách lịch sử không đồng nghĩa tách toàn bộ dữ liệu CV.
- Admin cũng không tự động được xem hội thoại của người khác.
- Tester không được gửi email, chạy Ops, tạo tài khoản hay sinh bộ câu hỏi phỏng vấn lưu vào DB. Các tool viết email/sinh câu hỏi được loại khỏi agent tester.
- Kiểm tra chủ sở hữu trước khi đọc state, ask, resume, đổi tiêu đề, xóa và lưu feedback.
- Không còn thread mặc định `default`; chương trình phải tạo hội thoại sau khi đăng nhập.
- Mật khẩu dùng scrypt và salt riêng; token phiên ngẫu nhiên chỉ lưu bản SHA-256 trong DB. Phiên hết hạn sau 12 giờ, bị thu hồi khi đăng xuất/khóa tài khoản/reset mật khẩu. Sai mật khẩu 5 lần khóa đăng nhập 15 phút.
- Phiên nằm trong Streamlit session; mở lại/reload làm mất session có thể cần đăng nhập lại. Chưa có “remember me”.

## 2. Áp dụng source và migration

Dừng Streamlit trước khi cập nhật. Sao lưu MySQL và `chat_history.db` trước migration; bản này chưa chạy migration trên DB thật của bạn.

Có thể tạo nhánh trước khi chép file:

```bash
git switch -c feature/auth-chat-ownership
```

Chép các file trong ZIP vào gốc dự án, sau đó chạy trong terminal tại thư mục `cv-rag-ai`:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONPATH=. python -m alembic upgrade head
PYTHONPATH=. python -m alembic current
```

Kết quả migration mong đợi: `0012 (head)`.

Migration thêm:

- `app_users`: tài khoản, mật khẩu băm, quyền, phòng ban, trạng thái và khóa đăng nhập.
- `auth_sessions`: token băm, người dùng, thời hạn.
- `chat_conversations.owner_user_id`: chủ sở hữu, có index và foreign key.
- `chat_conversations.deleted_at`: đánh dấu xóa để ngăn đọc lại kể cả khi dọn checkpoint lỗi.

Hội thoại cũ giữ nguyên, `owner_user_id = NULL`, chưa ai được đọc qua ứng dụng cho tới khi gán ở bước 4.

## 3. Tạo admin đầu tiên

```bash
PYTHONPATH=. python scripts/manage_users.py create sang --role admin
```

Nhập mật khẩu từ 12 đến 256 ký tự hai lần. Terminal không hiển thị mật khẩu khi gõ. Không có mật khẩu mặc định.

Lệnh quản trị local yêu cầu người vận hành có quyền truy cập source và cấu hình DB. Không expose các script này thành endpoint công khai.

## 4. Gán hội thoại cũ cho admin (tùy chọn)

```bash
PYTHONPATH=. python scripts/manage_users.py claim-legacy sang
```

Chỉ gán những hội thoại chưa có chủ sở hữu và chưa bị xóa. Lệnh không nhận tài khoản tester và không chuyển hội thoại đã thuộc người khác. Nếu lịch sử cũ thuộc nhiều người, không dùng lệnh gán hàng loạt này; cần đối chiếu chủ sở hữu trước.

## 5. Tạo tester

Xem phòng ban hiện có:

```bash
PYTHONPATH=. python scripts/manage_users.py departments
```

Lấy ID phòng ban dùng để demo, rồi chạy (thay `DEPARTMENT_ID` bằng ID thật):

```bash
PYTHONPATH=. python scripts/manage_users.py create tester_a --role tester --department-id DEPARTMENT_ID
PYTHONPATH=. python scripts/manage_users.py create tester_b --role tester --department-id DEPARTMENT_ID
```

Bạn cũng có thể đăng nhập admin, mở **Quản lý tài khoản** và tạo tester tại giao diện.

Tester bắt buộc có phòng ban tồn tại. Quyền CV đi theo `candidates.posting_id → job_postings.department_id`. CV chưa gắn job posting sẽ không hiện cho tester. Nếu chưa có phòng ban/job posting/CV phù hợp, cần chuẩn bị tập dữ liệu demo và gán qua quy trình quản lý/ingestion của dự án; bản cập nhật không tự chuyển toàn bộ CV thật vào phòng ban demo.

SQL chỉ đọc để kiểm tra số CV có trong từng phòng ban:

```sql
SELECT d.department_id, d.department_name, COUNT(c.candidate_id) AS cv_count
FROM departments d
LEFT JOIN job_postings p ON p.department_id = d.department_id
LEFT JOIN candidates c ON c.posting_id = p.posting_id
GROUP BY d.department_id, d.department_name;
```

## 6. Chạy và test giao diện

Khởi động các dịch vụ MySQL/Redis/Qdrant/MinIO như trước rồi chạy:

```bash
streamlit run app.py
```

| Kiểm tra       | Thao tác                                           | Kết quả mong đợi                                           |
| -------------- | -------------------------------------------------- | ---------------------------------------------------------- |
| Chưa đăng nhập | Mở localhost:8501                                  | Chỉ thấy form đăng nhập                                    |
| Admin          | Đăng nhập `sang`                                   | Thấy các tab và Quản lý tài khoản                          |
| Tester A       | Đăng nhập `tester_a`, tạo chat, hỏi một câu        | Có hội thoại riêng, không hiện tab email/Ops               |
| Tester B       | Dùng trình duyệt/profile khác đăng nhập `tester_b` | Không thấy hội thoại A                                     |
| Cùng phòng ban | Hai tester hỏi về CV demo cùng phòng ban           | Có thể dùng chung dữ liệu CV nhưng lịch sử vẫn tách        |
| Đăng xuất      | Đăng xuất A rồi đăng nhập B trong cùng trình duyệt | Không còn lịch sử/widget/nháp của A                        |
| Lịch sử bền    | A đăng nhập lại                                    | Hội thoại A vẫn tồn tại                                    |
| Xóa            | A xóa một hội thoại                                | Không còn trong danh sách; feedback và checkpoint được dọn |
| Khóa tài khoản | Admin khóa A, A thao tác/rerun                     | Phiên bị từ chối; phải được mở lại và đăng nhập mới        |
| Sai mật khẩu   | Sai 5 lần trên một tài khoản thử                   | Khóa đăng nhập 15 phút                                     |

Nếu thao tác AI đã bắt đầu trước lúc khóa tài khoản, tác vụ đang chạy có thể hoàn tất; các lần kiểm tra quyền tiếp theo sẽ từ chối phiên đó.

Để đổi mật khẩu hoặc mở khóa do nhập sai (không tự mở tài khoản bị admin vô hiệu hóa):

```bash
PYTHONPATH=. python scripts/manage_users.py reset-password tester_a
```

## 7. Test tự động

```bash
PYTHONPATH=. MYSQL_CONN=sqlite:// python -m pytest tests/test_auth.py tests/test_optimization.py -q --disable-warnings
```

Bộ test dùng SQLite tạm và model giả, không gửi email, không gọi Gemini, không sửa DB thật. Kiểm tra quyền bằng token đăng nhập thật trong test, gồm dùng thread của người khác, giả phòng ban, phiên hết hạn/thu hồi, legacy, xóa checkpoint, lỗi dọn checkpoint và migration lên/xuống. Có kiểm tra hồi quy optimizer.

Trong môi trường thực hiện: 20 tests passed. Đã compile Python thành công. Chưa chạy end-to-end với MySQL, Streamlit, Gmail và Gemini thật của bạn; cần thực hiện bước 6 trước khi chia sẻ link.

## 8. Ops CLI và tích hợp Python

Lệnh experiment giờ yêu cầu admin:

```bash
PYTHONPATH=. python scripts/run_ops_experiment.py PROPOSAL_ID --dataset cv-ops-extraction-test --username sang
```

Script hỏi mật khẩu, tạo phiên, chạy experiment và thu hồi phiên khi kết thúc.

Các script tự viết gọi chat/Ops/feedback trực tiếp phải có `auth_scope`:

```python
from getpass import getpass
from src.auth.service import login, logout, auth_scope
from src.chat.conversation_store import create_conversation
from src.interfaces.query_interface import query_candidates

token = login("tester_a", getpass("Password: "))
try:
    with auth_scope(token):
        thread_id = create_conversation()
        result = query_candidates("Ứng viên nào biết Python?", thread_id=thread_id)
        print(result)
finally:
    logout(token)
```

Khi xây FastAPI sau này, middleware/dependency phải xác thực token rồi mở scope cho từng request; không lấy role/user_id từ nội dung LLM hay trường tự khai của client.

## 9. Lưu trữ và phạm vi bản này

- `CHAT_HISTORY_PATH` tùy chọn, mặc định vẫn `chat_history.db`. Nếu đổi đường dẫn, chuyển file cũ tới đường dẫn mới và bảo đảm thư mục cha tồn tại. Giữ đường dẫn ổn định khi restart.
- Xóa hội thoại đánh dấu tombstone trong MySQL trước khi dọn SQLite. Nếu dọn lỗi, không khôi phục quyền đọc; kiểm tra/dọn lại checkpoint trước khi coi là đã xóa vật lý hoàn toàn. Request đang chạy đồng thời cũng có thể ghi thêm checkpoint sau bước dọn, nhưng tombstone vẫn chặn truy cập.
- Worker gửi email là tiến trình backend tin cậy; lệnh dispatch từ ứng dụng kiểm tra admin. Không expose broker/DB ra Internet.
- Chưa thay Dockerfile, chưa thêm FastAPI, chưa xây Next.js/NestJS và chưa deploy. Dockerfile cũ vẫn cần chỉnh ở bước triển khai.
- Đây là bản cho một ứng dụng Streamlit demo; cần thiết kế lưu checkpoint dùng chung và kiểm thử tải trước khi chạy nhiều replica.
