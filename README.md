# CV RAG AI/Data — DB Migration

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # chỉnh MYSQL_CONN cho khớp docker-compose ở bước trước
```

## Chạy migration (cần MySQL đang chạy — xem docker-compose.yml đã tạo trước đó)

```bash
alembic upgrade head
```

## Kiểm tra

```bash
alembic current
alembic history
```

## Tạo migration mới sau này (khi sửa models.py)

```bash
alembic revision --autogenerate -m "mo ta thay doi"
alembic upgrade head
```

## Luồng tiếp nhận CV qua Gmail

### Setup Gmail API (làm 1 lần)

1. Vào Google Cloud Console, tạo project (hoặc dùng project có sẵn của công ty).
2. Bật **Gmail API** trong thư viện API.
3. Tạo OAuth Client ID loại **Desktop app**, tải file `credentials.json` về, đặt vào thư mục gốc project (hoặc chỉnh `GMAIL_CREDENTIALS_PATH` trong `.env`).
4. Chạy lần đầu bằng chính tài khoản Gmail HR (script sẽ tự mở trình duyệt để đăng nhập):
   ```bash
   python scripts/poll_gmail_intake.py
   ```
   Sau khi đăng nhập xong, file `token.json` được sinh ra tự động — các lần chạy sau không cần đăng nhập lại (tự refresh token).

### Chạy thử pipeline

```bash
python scripts/poll_gmail_intake.py
```

### Chạy định kỳ — dùng Celery Beat (khuyến nghị, thay cho cron)

Cần 3 process chạy song song (3 terminal riêng, hoặc 3 service riêng khi lên Docker sau này):

```bash
# Terminal 1 — Celery Worker: nhận và xử lý task (poll email, parse CV sau này)
celery -A src.workers.celery_app worker --loglevel=info

# Terminal 2 — Celery Beat: đến giờ thì tự đẩy task poll_email_intake vào queue
celery -A src.workers.celery_app beat --loglevel=info
```

Không cần chạy `scripts/poll_gmail_intake.py` bằng tay hay cấu hình cron ngoài hệ điều hành nữa — Beat tự động gọi `poll_email_intake` mỗi 2 phút (cấu hình trong `src/workers/celery_app.py`, đổi lịch bằng cách sửa `crontab(minute="*/2")`).

`scripts/poll_gmail_intake.py` vẫn giữ lại để chạy tay/debug nhanh khi cần, không phụ thuộc Celery.

### Luồng chuyển tiếp sang Parsing (Luồng A + B)

Ngay sau khi 1 CV hợp lệ được ghi vào `ingestion_jobs`, pipeline tự động dispatch task `process_cv_job` vào Celery Queue — Worker ở Terminal 1 sẽ tự nhặt lên xử lý tiếp: parse → classify → extract → chunk → embed → index (xem chi tiết ở mục "Luồng A + B" bên dưới).

### Quy ước tên file bắt buộc

Mặc định: `HoTen_ViTriUngTuyen_CV.pdf` (chỉnh qua `CV_FILENAME_PATTERN` trong `.env`).
File sai tên/định dạng sẽ bị ghi vào `ingestion_jobs` với `status='rejected'` kèm `error_message`, không tốn resource xử lý tiếp.

## Luồng A + B — Parsing, Extraction, Chunking, Indexing

Toàn bộ dùng **Gemini** (miễn phí) cho cả LLM extraction lẫn Embedding — không dùng Claude/Anthropic ở phần này.

### Setup lần đầu

```bash
pip install -r requirements.txt
# Lấy API key miễn phí tại https://aistudio.google.com/apikey, điền GOOGLE_API_KEY vào .env
python scripts/init_qdrant_collection.py   # tạo collection cv_chunks 1 lần
```

### Cách hoạt động

Khi 1 CV được `EmailIntakePipeline` chấp nhận (Luồng 1), nó tự dispatch task `process_cv_job` — task này chạy `src/ingestion/pipeline.py`:

```
Load file MinIO -> Parse PDF (PyMuPDF) -> Check text hợp lệ
  -> Classify có phải CV không (gemini-3.5-flash-lite, rẻ)
  -> Check trùng nội dung (text hash)
  -> LLM Structured Extraction (gemini-3.5-flash)
  -> Ghi candidates + bảng con (MySQL)
  -> Build Document theo section -> Embed (gemini-embedding-001, 768 chiều) -> Upsert Qdrant
  -> status = 'indexed'
```

**Lưu ý về model:** cố tình KHÔNG dùng `gemini-2.5-flash`/`gemini-2.5-flash-lite` dù đang miễn phí, vì Google sẽ shutdown 2 model này vào 16/10/2026 — dùng thế hệ `gemini-3.5-flash` / `gemini-3.5-flash-lite` để khỏi phải đổi model giữa chừng dự án.

### Retry / DLQ

- Lỗi **bản chất** (không phải CV, PDF hỏng, thiếu tên) → `status='rejected'` ngay, không retry.
- Lỗi **tạm thời** (mạng, MinIO, LLM timeout) → retry có backoff mũ (tối đa 15 phút giữa các lần), vượt `max_attempts` (mặc định 3) → `status='dlq'`.

### Verify

```bash
docker exec -it cvrag-mysql mysql -uadmin -p123456 cv_rag_db \
  -e "SELECT job_id, status, candidate_id FROM ingestion_jobs ORDER BY created_at DESC LIMIT 5;"

docker exec -it cvrag-mysql mysql -uadmin -p123456 cv_rag_db \
  -e "SELECT candidate_id, full_name, total_years_experience FROM candidates;"
```

Kiểm tra Qdrant có point chưa: mở `http://localhost:6333/dashboard`, xem collection `cv_chunks`.

## Xoay vòng nhiều Gemini API key (tránh hết quota)

Điền `GOOGLE_API_KEY`, `GOOGLE_API_KEY_2`, `GOOGLE_API_KEY_3`... vào `.env` (mỗi biến 1 key thật khác nhau, tạo trên `aistudio.google.com/apikey`). Hệ thống tự dùng key đầu tiên tới khi gặp lỗi hết quota (HTTP 429) mới tự động chuyển sang key kế tiếp (chiến lược failover, không phải round-robin) — không cần sửa gì thêm, `src/llm/key_manager.py` xử lý tự động cho mọi lời gọi Gemini (extraction, embedding, agent, evaluation).

Chỉ điền 1 key vẫn chạy bình thường — nhiều key chỉ là tùy chọn để tăng tổng quota khả dụng.

## Giao diện demo — Streamlit

```bash
streamlit run app.py
```

Mở `http://localhost:8501`, có 4 tab:

- **Hỏi đáp** — chat với Agent (10 tool), có **sidebar lịch sử hội thoại giống Claude/Gemini**: bấm "➕ Cuộc trò chuyện mới" để tạo hội thoại mới, bấm vào 1 hội thoại cũ trong danh sách để xem lại và hỏi tiếp (Agent vẫn nhớ ngữ cảnh cũ), bấm 🗑️ để xóa. Lịch sử lưu bền vào file `chat_history.db` (SQLite), sống sót qua restart app — không mất khi tắt server. Danh sách hội thoại dùng chung cho mọi người mở app (demo nội bộ, chưa có đăng nhập).
- **Đánh giá theo JD** — nhập `candidate_id` + JD (gõ tay hoặc upload PDF), xem điểm chấm theo rubric cố định
- **Top-K theo JD** — đưa 1 JD vào (gõ tay hoặc PDF), hệ thống tự tìm và chấm điểm chi tiết những ứng viên phù hợp nhất trong toàn hệ thống (tối đa 10 người)
- **Danh sách ứng viên** — browse nhanh, lọc theo kỹ năng, xem ảnh chân dung (nếu tách được), copy `candidate_id` để dùng ở các tab khác

## CV dạng ảnh scan (OCR fallback)

Nếu PDF không có text layer (CV chụp/scan), hệ thống tự động render trang thành ảnh và gửi cho Gemini (multimodal) đọc chữ, thay vì dùng thư viện OCR riêng. Không cần cấu hình gì thêm — tự kích hoạt khi text extract được quá ngắn (`CV_MIN_TEXT_LENGTH`).

**Ảnh chân dung** cũng được thử tách ra (best-effort, dựa trên heuristic kích thước/tỷ lệ ảnh nhúng trong PDF — không đảm bảo chính xác 100%), lưu vào MinIO (`photos/{candidate_id}.jpg`), đường dẫn lưu ở cột `candidates.photo_object_key`. Không có ảnh cũng không sao — không phải lỗi.

## JD có cấu trúc + Top-K matching

JD (dù gõ tay hay từ PDF) được trích xuất thành dữ liệu có cấu trúc (`JDSchema`: vị trí, kỹ năng bắt buộc, số năm KN tối thiểu) trước khi dùng. Tool `find_top_candidates_for_jd` (Agent) và tab "Top-K theo JD" (Streamlit) dùng dữ liệu này để: lọc cứng bằng SQL trước → xếp hạng ngữ nghĩa (hybrid search + rerank) → chấm điểm chi tiết cho đúng top K (tối đa 10, giới hạn để không tốn quota quá mức).

## Phân quyền theo phòng ban

Thêm bảng `departments`/`job_postings`, mỗi candidate được best-effort khớp vào 1 `posting_id` dựa theo `applied_position` (text tự do LLM extract). Để giới hạn Agent chỉ thấy dữ liệu 1 phòng ban:

```python
from src.interfaces.query_interface import query_candidates
result = query_candidates("Ứng viên nào biết Python?", department_id="<id>")
```

`department_id` được **ép buộc ở tầng DB** (qua `contextvars`, xem `retrieval/access_scope.py`), không phải tham số Agent tự chọn — LLM không nhìn thấy và không thể bỏ qua giới hạn này.

Seed department/posting ban đầu (chưa có UI quản lý, dùng script/Python trực tiếp):

```python
from src.retrieval.department_store import create_department, create_job_posting
dept_id = create_department("Engineering")
create_job_posting(dept_id, "Data Engineer")
```

## Xoay vòng key qua Redis (đồng bộ nhiều Celery worker)

`ApiKeyManager` giờ lưu index key đang dùng vào Redis thay vì biến trong process — chạy nhiều worker (`celery worker --concurrency=N` hoặc nhiều instance) vẫn dùng chung đúng 1 trạng thái xoay vòng, tránh mỗi worker tự đoán key khác nhau.

## Feedback 👍/👎

Mỗi câu trả lời trong tab Hỏi đáp có nút 👍/👎, lưu vào bảng `chat_feedback`. Lấy các câu bị 👎 để bổ sung eval dataset:

```python
from src.chat.feedback_store import get_negative_feedback_examples
print(get_negative_feedback_examples(limit=20))
```

## Chuẩn hóa từ đồng nghĩa khi search

`retrieval/skill_normalizer.py` — search "Postgres" tự động khớp luôn "PostgreSQL", "psql"... Chỉ áp dụng ở tầng truy vấn, không sửa dữ liệu gốc đã lưu. Mở rộng thêm từ đồng nghĩa trong `SKILL_SYNONYMS` khi phát hiện case bị sót.

## Unit test

```bash
pytest tests/ -v
```

Có test cho `key_manager.py` (bao gồm test đồng bộ Redis giữa nhiều "worker" giả lập) và `candidate_ranking.py` (mock toàn bộ DB/Qdrant/Gemini, chỉ test logic ghép 3 bước).

## `ingestion_interface.py` — nhận CV ngoài kênh email

```python
from src.interfaces.ingestion_interface import submit_cv_for_ingestion
result = submit_cv_for_ingestion(file_bytes, filename="NguyenVanA_DataEngineer_CV.pdf", source_type="web_upload")
```

Chạy qua đúng bộ validate 5 cửa + dedupe content hash, dùng chung `process_cv_job` với luồng email — không có pipeline xử lý riêng cho nguồn khác email.

## Gửi email mời phỏng vấn — có xác nhận người, không tự động

Agent (chat) CHỈ soạn nháp nội dung (tool `draft_interview_invitation`), KHÔNG BAO GIỜ tự gửi email thật — kể cả khi HR yêu cầu trực tiếp trong chat. Gửi thật phải qua tab riêng **"✉️ Gửi thư mời"**: soạn nháp → HR xem/sửa → tick xác nhận → bấm gửi.

**Cần re-auth Gmail** vì đã thêm scope `gmail.send` (trước chỉ có `gmail.modify`):

```bash
rm token.json
python scripts/poll_gmail_intake.py --dry-run   # đăng nhập lại, xin quyền gửi mail mới
```

Mọi email đã gửi thật được log vào bảng `sent_emails` (candidate_id, subject, body, gmail_message_id, sent_at) — tránh gửi trùng (có cảnh báo nếu candidate đã từng nhận mail trước đó, không tự động chặn cứng, để HR tự quyết).
