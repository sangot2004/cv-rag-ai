# CV RAG AI — Tổng kết quá trình xây dựng dự án

Từ pipeline xử lý CV đến ứng dụng web và GitLab Container Registry

Ngày tổng hợp: 30/10/2026
Repository: cv-rag-ai
Nhánh tích hợp hiện tại: feature/fastapi-core
Commit đối chiếu: 49304b4 — merge ci/docker-registry

## 1. Phạm vi và trạng thái hiện tại

Tài liệu tổng hợp các bước đã thực hiện và trao đổi trong quá trình phát triển CV RAG Agentic: nền tảng dữ liệu, xử lý CV, AI truy vấn, tối ưu vận hành, phân quyền, quản lý prompt, FastAPI, frontend, Docker, kiểm thử và GitLab CI/Container Registry. Mục đích là cung cấp một hồ sơ dự án có thể dùng để báo cáo, trình bày, bàn giao và lập kế hoạch triển khai tiếp.

Thông tin được đối chiếu với hội thoại, source hiện tại, lịch sử Git và tài liệu trong repository. Những bước nền tảng đã có từ trước được ghi nhận là nền móng của dự án, không quy toàn bộ thành phần cho một lần triển khai. Các mốc không có ngày xác thực được trình bày theo thứ tự phát triển, không tự gán ngày hoàn thành.

Kết quả chính tại thời điểm tổng hợp:

- Có ứng dụng tuyển dụng với Next.js/BFF, FastAPI và Celery, bên cạnh giao diện Streamlit dùng trong giai đoạn đầu.
- Có tiếp nhận CV qua Gmail và web, trích xuất dữ liệu, lưu hồ sơ, lập chỉ mục và tìm kiếm bằng hội thoại.
- Có phân quyền admin/tester, dữ liệu CV theo phòng ban và lịch sử hội thoại riêng theo tài khoản.
- Có JD/Top-K trong chat, câu hỏi phỏng vấn dựa trên CV, soạn và duyệt thư mời, gửi hàng loạt và lịch sử gửi.
- Có System Ops, cấu hình extraction có phiên bản, cache, đề xuất tối ưu, experiment, duyệt và rollback.
- Có bộ kiểm thử 220 backend tests và 57 browser tests được ghi nhận; pipeline MR đã hiển thị tổng 277 tests.
- Có pipeline GitLab gồm 6 job và hai repository image backend/frontend trên Container Registry, mỗi repository có một tag theo ảnh người dùng cung cấp.
- Chưa ghi nhận triển khai lên VPS/domain công khai; chưa có job deploy tự động hoặc nút deploy đã triển khai trong CI.

Mốc kiểm chứng cần phân biệt: source hiện có chứng minh tính năng đã được cài đặt; kết quả test tự động chứng minh các tình huống đã kiểm thử; screenshot GitLab chứng minh trạng thái pipeline/Registry tại thời điểm chụp. Những bằng chứng đó chưa thay thế nghiệm thu chất lượng AI và vận hành thực tế trên máy chủ công khai.

## 2. Mục tiêu sản phẩm và kiến trúc tổng thể

Mục tiêu là giúp bộ phận tuyển dụng nhận và tổ chức CV, tìm người phù hợp bằng ngôn ngữ tự nhiên, so sánh với yêu cầu tuyển dụng, chuẩn bị phỏng vấn và quản lý thư mời. Người quản trị kiểm soát các thao tác có tác động như gửi email, thay đổi phạm vi hồ sơ và áp dụng cấu hình AI.

### 2.1. Các thành phần

| Thành phần | Vai trò trong hệ thống |
| --- | --- |
| Next.js, React, TypeScript | Giao diện web, điều hướng, biểu mẫu, trạng thái tải/lỗi và giao diện responsive |
| Next.js BFF | Nhận request từ trình duyệt, quản lý cookie phiên và chuyển tiếp đến FastAPI theo allowlist |
| FastAPI | API nghiệp vụ, validation, xác thực, phân quyền, hợp đồng response và xử lý lỗi |
| LangChain/LangGraph | Điều phối agent, gọi tool, lưu trạng thái hội thoại và tạm dừng để xác nhận JD |
| Gemini | Classification, extraction, OCR, embedding và các tác vụ sinh nội dung/đánh giá theo cấu hình |
| LangSmith | Lưu prompt theo commit, hỗ trợ tracing và dataset cho kiểm chứng |
| MySQL/SQLAlchemy/Alembic | Hồ sơ và bảng con, tài khoản, phiên, metadata hội thoại, jobs, email và dữ liệu Ops |
| SQLite checkpoint | Lưu trạng thái LangGraph và lịch sử phục hồi hội thoại |
| Qdrant | Lưu vector của các đoạn CV phục vụ truy vấn ngữ nghĩa |
| Redis | Broker Celery, extraction cache và trạng thái dùng chung của key manager |
| MinIO | Lưu file CV gốc và ảnh chân dung trích xuất được |
| Celery worker/Beat | Xử lý tác vụ nền, lịch tiếp nhận Gmail và phục hồi outbox khi bật scheduler |
| Docker Compose/Caddy | Khởi chạy stack demo, lưu volume và reverse proxy HTTPS |
| GitLab CI/Registry | Kiểm tra code, build image và lưu phiên bản image theo commit |

### 2.2. Ba luồng xuyên suốt

Luồng xử lý CV: Gmail hoặc upload web → kiểm tra file → MinIO và ingestion job → Celery → parse/OCR → classification → extraction → MySQL → chunk/embedding → Qdrant → hồ sơ có thể tra cứu.

Luồng hỏi đáp: trình duyệt → Next BFF → FastAPI → kiểm tra phiên và phòng ban → LangGraph agent/tool → SQL và retrieval → câu trả lời/thẻ kết quả → checkpoint và lịch sử riêng.

Luồng phát hành: push nhánh → kiểm thử → build thử image → MR → kiểm thử MR → merge feature/fastapi-core → kiểm thử và build image → push Container Registry. Phần kéo image và vận hành trên máy chủ là giai đoạn tiếp theo.

## 3. Giai đoạn nền tảng — dữ liệu và tiếp nhận CV

### 3.1. Các bước đã hình thành

1. Thiết lập cấu trúc Python, cấu hình môi trường và các dịch vụ MySQL, Redis, Qdrant, MinIO.
2. Xây schema lưu ứng viên, kỹ năng, kinh nghiệm, học vấn; mở rộng thêm chứng chỉ, dự án và thông tin ảnh.
3. Quản lý thay đổi schema bằng migration Alembic thay vì sửa database thủ công từng lần.
4. Tích hợp Gmail OAuth, đọc email và lấy file CV đính kèm.
5. Kiểm tra tên, định dạng và tính hợp lệ của file; lưu file được tiếp nhận vào MinIO và ghi ingestion job.
6. Đưa job sang Celery để xử lý nền; bổ sung Beat cho lịch polling khi cần vận hành định kỳ.
7. Có interface tiếp nhận CV dùng chung để nguồn web và email đi vào cùng pipeline nghiệp vụ.

Điểm quan trọng là tiếp nhận file và xử lý thành công là hai trạng thái khác nhau. Việc tạo job hoặc trả HTTP 202 chỉ xác nhận hệ thống đã nhận yêu cầu; hồ sơ chỉ sẵn sàng khi pipeline hoàn tất và job đạt trạng thái indexed.

### 3.2. Kết quả và file chính

Các nhóm mã gồm src/db/, src/storage/, src/ingestion/, src/interfaces/ và src/workers/. Script scripts/poll_gmail_intake.py phục vụ chạy tay/debug; lịch chạy nền nằm trong cấu hình Celery.

MinIO giữ dữ liệu nhị phân, MySQL giữ dữ liệu nghiệp vụ và metadata. Việc tách hai vai trò giúp hồ sơ có cấu trúc và file CV gốc được quản lý nhất quán mà không đưa file PDF vào các cột dữ liệu nghiệp vụ.

## 4. Giai đoạn AI dữ liệu — parse, extraction và retrieval

### 4.1. Hoàn thiện pipeline CV

1. Đọc PDF bằng PyMuPDF để lấy text.
2. Khi text layer không đủ, bổ sung OCR fallback sử dụng khả năng đọc ảnh của model.
3. Phân loại tài liệu để xác định có phải CV trước khi trích xuất sâu.
4. Kiểm tra trùng nội dung và trích xuất dữ liệu theo CVSchema.
5. Ghi ứng viên và các bảng con vào MySQL.
6. Tạo document/chunk theo phần của CV, sinh embedding và upsert Qdrant.
7. Cập nhật trạng thái xử lý, số lần thử và nguyên nhân lỗi an toàn để vận hành có thể theo dõi.

Các lỗi không thể xử lý bằng retry, như file hỏng hoặc tài liệu bị từ chối, được phân biệt với lỗi tạm thời như timeout/mạng. Sau khi vượt số lần thử, job có thể vào DLQ để người quản trị kiểm tra.

Ảnh chân dung được thử tách từ ảnh nhúng trong PDF theo heuristic và lưu MinIO. Đây là best-effort: có CV không có ảnh hoặc không thể xác định đúng ảnh chân dung; UI cần có trạng thái thay thế thay vì coi là hồ sơ hỏng.

### 4.2. Tìm kiếm và công cụ agent

Hệ thống kết hợp truy vấn SQL cho điều kiện có cấu trúc, tìm kiếm từ khóa BM25, vector search và reranking. Chuẩn hóa tên kỹ năng giúp truy vấn các cách viết tương đương mà không sửa dữ liệu gốc.

Agent có các công cụ tra cứu, danh sách ứng viên mới, chi tiết hồ sơ, lọc kỹ năng, chứng chỉ/dự án, thống kê, so sánh và đánh giá. Quyền truy cập được gắn vào tầng nghiệp vụ/truy vấn để yêu cầu trong prompt không thể tự đổi phòng ban.

Nhóm mã tiêu biểu: src/ingestion/extraction/, src/ingestion/embedding/, src/retrieval/, src/agent/tools/ và src/agent/agent_executor.py.

## 5. Giai đoạn trợ lý tuyển dụng — Streamlit, JD và hành động có xác nhận

### 5.1. Giao diện và lịch sử ban đầu

Streamlit được dùng để thử nghiệm nhanh pipeline và agent, với các chức năng chat, xem ứng viên, đánh giá JD/Top-K, email, phỏng vấn và Ops được bổ sung qua từng đợt. Hội thoại được lưu bền bằng checkpoint SQLite và metadata MySQL; feedback tốt/xấu được ghi để phục vụ đánh giá sau này.

### 5.2. JD và Top-K

1. Nhận JD dạng văn bản hoặc tài liệu trong luồng hỗ trợ tương ứng.
2. Trích xuất tiêu chí như vị trí, kỹ năng bắt buộc và kinh nghiệm tối thiểu.
3. Dùng LangGraph interrupt để dừng trước bước xếp hạng và chờ người dùng xem/sửa/xác nhận.
4. Sau xác nhận, áp dụng lọc SQL, retrieval/rerank và đánh giá các ứng viên được chọn.
5. Trả Top-K với giới hạn tối đa 10 người; điểm đánh giá sử dụng thang 1–5.

Việc xác nhận là một phần của trạng thái graph, có thể phục hồi khi tải lại; không chỉ là câu nhắc trong prompt. Hủy ở đây là hủy quyết định đang chờ xác nhận, không đồng nghĩa có cơ chế dừng mọi lời gọi AI đang chạy.

### 5.3. Thư mời và câu hỏi phỏng vấn

Agent được hỗ trợ soạn nháp thư mời; gửi thật phải qua thao tác duyệt của người dùng. Gửi nhiều thư được đưa sang worker, theo dõi kết quả từng người nhận và lịch sử gửi.

Bộ câu hỏi phỏng vấn được sinh từ nội dung CV thật và có evidence_quote. Hệ thống kiểm tra trích dẫn có khớp raw_text trước khi lưu; câu có bằng chứng không hợp lệ bị loại. Nếu toàn bộ câu đầu tiên bị loại, có cơ chế thử sinh lại một lần.

Các chức năng upload tài liệu ngay trong chat từng có ở Streamlit không được mặc định xem là đã có đầy đủ trên Next.js. Frontend hiện có kênh upload CV riêng; cần đọc phạm vi từng giao diện khi demo.

## 6. System Ops — đo usage, giá và tối ưu extraction

### 6.1. Phase 1–2: đo lường và giám sát

1. Gắn telemetry vào các lời gọi model: classification, extraction, OCR, JD, chat, email và phỏng vấn.
2. Ghi nhận embedding riêng vì đi qua SDK trực tiếp; đây là điểm được rà lại khi chi phí không hiển thị như mong đợi.
3. Lưu model, module, token, latency, trạng thái, liên kết operation/job/candidate/thread khi có.
4. Cấu hình bảng giá theo đúng tên model và phiên bản giá để ước tính chi phí.
5. Xây dashboard theo thời gian/module/model, tổng token, chi phí đã biết, mức thiếu dữ liệu, lỗi, latency và cảnh báo.

Phân biệt ba trường hợp: thiếu usage là chưa có số liệu; thiếu giá là chưa tính được chi phí; giá được cấu hình bằng 0 là trường hợp free tier. Giá 0 không phải lỗi vì số tiền quá nhỏ. Với Gemini free, vẫn đo được calls/token/thời gian khi provider trả usage, nhưng không thể suy từ đó ra khoản tiền thực tế tiết kiệm được.

Chi phí là ước tính theo cấu hình được snapshot khi ghi log, không phải hóa đơn provider. Latency model không bao gồm toàn bộ thời gian chờ queue, parse, rerank và người dùng xác nhận.

### 6.2. Phase 3: tối ưu cách AI chạy

1. Thêm cache extraction trong Redis.
2. Xây khóa cache theo nội dung CV và cấu hình liên quan, gồm model, prompt thực dùng và schema.
3. Cho phép quản lý cấu hình model extraction theo phiên bản.
4. Bổ sung cấu hình retrieval overfetch ở tầng hệ thống.

Nếu đầu vào/cấu hình giống nhau, cache có thể tránh gọi model lại. Khi model, prompt hoặc schema đổi, cache cũ không được coi là kết quả tương đương.

### 6.3. Phase 4: đề xuất, kiểm chứng và duyệt

1. Admin tạo đề xuất thủ công hoặc yêu cầu AI phân tích usage.
2. Chạy paired experiment: baseline và proposal dùng cùng dataset CV có đáp án chuẩn.
3. So sánh chất lượng, token, latency và chi phí khi có đủ usage/giá.
4. Backend kiểm tra report đạt điều kiện và baseline vẫn khớp trước khi Approve.
5. Admin duyệt để kích hoạt; có rollback về cấu hình được phép.

Phạm vi MVP tập trung vào extraction. Điểm chất lượng được tính bằng code so với đáp án chuẩn, chưa có LLM judge, routing độ khó hoặc experiment retrieval. Runner gọi model trực tiếp nên chưa chứng minh mức cache hit/tiết kiệm Redis bằng experiment; đề xuất chỉ bật cache có thể đủ điều kiện theo quy tắc hiện tại khi chất lượng đạt. AI không tự áp dụng đề xuất vào cấu hình chạy.

## 7. Xác thực, quyền phòng ban và lịch sử riêng

### 7.1. Các bước triển khai

1. Thêm app_users, auth_sessions và liên kết chủ sở hữu hội thoại.
2. Tạo admin đầu tiên qua scripts/manage_users.py; mật khẩu được nhập kín trong terminal.
3. Băm mật khẩu bằng scrypt/salt, lưu hash token phiên thay cho token thô trong database.
4. Phân vai admin/tester; tester bắt buộc gắn phòng ban.
5. Kiểm tra quyền trước đọc/gửi/resume/feedback/xóa hội thoại.
6. Thêm khóa/mở tài khoản, reset mật khẩu và thu hồi phiên.
7. Khi xóa hội thoại, lưu deleted_at, dọn feedback và checkpoint, có đường xử lý nếu cleanup chưa xong.

Phiên mặc định có thời hạn 12 giờ; nhập sai 5 lần gây khóa đăng nhập 15 phút. Người dùng đã thử tạo admin, hai tester, kiểm tra đăng nhập/lịch sử riêng và báo các bước hoạt động ổn. Ban đầu hai tester cùng Engineering và dữ liệu Sales trống, nên bài thử đó chưa đủ chứng minh tách CV giữa hai phòng ban; bài test Docker sau này đã dùng hai phòng ban với dữ liệu riêng.

Lỗi so sánh datetime naive/aware được xử lý bằng thống nhất biểu diễn UTC cho thời gian database. Trong source hiện tại, thời gian so sánh được chuẩn hóa qua helper trước khi kiểm tra expires_at/locked_until.

### 7.2. Ma trận quyền hiện tại

| Chức năng | Admin | Tester |
| --- | --- | --- |
| Chat, lịch sử và feedback | Hội thoại của chính mình | Hội thoại của chính mình |
| Danh sách/chi tiết/ảnh ứng viên | Theo quyền quản trị | Chỉ ứng viên thuộc phòng ban được cấp |
| JD/Top-K trong chat | Trong phạm vi được phép | Trong phạm vi phòng ban |
| Soạn, duyệt và gửi thư | Có | Không |
| Sinh/quản lý bộ câu hỏi phỏng vấn | Có | Không |
| Upload CV, jobs, quản trị tài khoản/phòng ban/vị trí | Có | Không |
| Dashboard Ops, experiment, Approve/rollback | Có | Không |

Admin không mặc nhiên được đọc hội thoại riêng của người khác. Hai tester cùng phòng ban có thể thấy cùng CV nhưng vẫn có lịch sử riêng. CV chưa gắn vị trí tuyển dụng không tự xuất hiện cho tester.

## 8. Quản lý prompt trên LangSmith

### 8.1. Quá trình chuyển đổi

1. Thử đưa prompt lên LangSmith và kiểm tra nội dung qua giao diện quản lý prompt.
2. Viết thử việc kéo prompt về, chạy extraction với PDF mẫu để kiểm tra biến đầu vào/schema.
3. Chuyển các điểm sử dụng prompt sang lớp src/llm/prompt_store.py.
4. Ghim commit của prompt thay vì tự động dùng bản mới nhất.
5. Kiểm tra kiểu template, định dạng, tập biến, nội dung và metadata commit khi tải về.
6. Nối commit extraction vào cấu hình Ops, experiment, cache và rollback.

Hiện source khai báo 9 prompt: classify CV, extract CV, OCR ảnh CV, extract JD, agent system, evaluate candidate, draft interview email, generate interview questions và optimization analysis.

Source vẫn giữ tên prompt, commit đã ghim, biến đầu vào, schema, logic kiểm tra và cách gọi. Việc dùng LangSmith không có nghĩa toàn bộ chuỗi hướng dẫn/docstring trong source đều biến mất. Các script upload prompt giai đoạn thử nghiệm đã được bỏ sau chuyển đổi; scripts/check_langsmith_prompts.py còn dùng để kiểm tra quyền truy cập và commit.

### 8.2. Lợi ích và đánh đổi

Prompt có thể được quản lý, xem phiên bản và thử nghiệm tập trung. Ghim commit giúp biết chính xác prompt nào tạo kết quả và quay về bản đã kiểm chứng khi cần. Cache extraction gắn với prompt thực dùng giúp tránh tái sử dụng kết quả từ prompt khác.

Đổi lại, ứng dụng phụ thuộc vào quyền truy cập LangSmith khi cần tải prompt; các process đang cache prompt không tự cập nhật theo mọi chỉnh sửa trên giao diện. Tắt tracing không đồng nghĩa bỏ nhu cầu API key đọc prompt. Việc tối ưu chi phí hoặc chất lượng vẫn cần đo trên dữ liệu đại diện.

## 9. Tách backend FastAPI để phục vụ frontend

### 9.1. Các bước thực hiện

1. Đọc và góp ý tài liệu API trước khi triển khai.
2. Tạo nhánh feature/fastapi-core và đặt cấu trúc route/schema/dependency/middleware rõ ràng.
3. Tách điều phối chat thành service dùng chung với logic hiện có.
4. Thêm API health, login/me/logout, tạo/liệt kê/đọc/xóa hội thoại, gửi tin, resume và feedback.
5. Chuẩn hóa request ID, lỗi an toàn và các mã HTTP để frontend có thể phục hồi đúng.
6. Giữ trạng thái JD confirmation bền theo checkpoint, hỗ trợ nhiều confirmation_id trong một lượt.
7. Kiểm tra từng nhóm bằng Swagger, sau đó bổ sung integration tests và API cho các module tuyển dụng/quản trị.

Các nhóm API hiện có nằm trong src/api/routes/: auth, conversations, chat, candidates, interviews, emails, management, ingestion, ops và health. DTO/schemas nằm trong src/api/schemas/; nghiệp vụ nằm ở các service tương ứng.

### 9.2. Các quyết định quan trọng

- API xác định người dùng và phòng ban từ phiên, không tin role/owner do client tự gửi.
- ID hội thoại cũ được hỗ trợ dưới dạng chuỗi định danh hợp lệ; không ép mọi thread lịch sử thành UUID.
- Khóa thao tác cùng hội thoại giúp tránh ghi đồng thời; phạm vi hiện tại vẫn yêu cầu một tiến trình API ghi chat.
- Khi request có kết quả chưa rõ, client đọc lại trạng thái thay vì tự gửi lại tác vụ AI.
- EXECUTION_INCOMPLETE là trạng thái cần xử lý phục hồi/hội thoại mới theo contract, không coi mọi HTTP 409 là lỗi định dạng.
- Lịch sử có thể đọc mà không cần khởi tạo model hoặc tải prompt để sinh lại câu trả lời.

Thời điểm chuyển sang frontend, API chat chủ yếu là request/response; không mô phỏng việc streaming từng token như thể backend đang streaming thật.

## 10. Thiết kế và xây frontend Next.js/BFF

### 10.1. Từ thiết kế đến cấu trúc code

1. Lập kế hoạch FE với sitemap, vai trò, các màn hình và trạng thái loading/empty/error.
2. Tiếp nhận screenshot, HTML và tài liệu design do người dùng tạo bằng công cụ thiết kế AI.
3. Đối chiếu prototype với dữ liệu/quyền/API thực tế, chỉnh login, shell admin/tester, chat, JD confirmation và mobile.
4. Chọn thư mục frontend/ trong cùng repository để phát triển cùng backend.
5. Dựng Next.js, TypeScript, React, TanStack Query, Zod và các thành phần UI dùng chung.
6. Xây BFF, auth gate, cookie phiên và adapter lỗi trước khi nối các module nghiệp vụ.
7. Tích hợp từng module rồi kiểm tra cả quyền API, hành vi trình duyệt và responsive.

### 10.2. Xác thực trên web

Trình duyệt gọi route cùng origin của Next. BFF giữ token backend qua cookie HttpOnly; bản HTTPS production dùng cookie Secure. Bearer token không được trả cho mã JavaScript frontend qua JSON login. Các mutation được kiểm tra Origin; route proxy có allowlist; dữ liệu nhạy cảm dùng private/no-store.

Khi logout hoặc đổi tài khoản, frontend xóa dữ liệu phiên/query/draft liên quan để tránh hiển thị nội dung tài khoản trước. Backend vẫn là nơi quyết định quyền, kể cả khi người dùng truy cập URL trực tiếp.

### 10.3. Hoàn thiện trải nghiệm

Giao diện được làm mềm hơn bằng màu nền dịu, thẻ bo góc, khoảng cách nhất quán, trạng thái hover/focus và chuyển động có kiểm soát. Có hỗ trợ reduced motion, sidebar thu gọn, menu mobile đóng khi điều hướng bằng chuột hoặc bàn phím, bộ lọc nâng cao và skeleton/loading.

Các trạng thái lỗi, 404 và tải trang có thông điệp tiếng Việt cùng hành động phục hồi. Markdown câu trả lời được render bằng react-markdown/remark-gfm, có kiểm soát HTML/link và bảng cuộn để không làm vỡ bố cục mobile.

## 11. Các màn hình nghiệp vụ đã tích hợp

### 11.1. Chat, JD/Top-K và liên kết hồ sơ

Quyết định sản phẩm là giữ đánh giá JD và Top-K trong ô hỏi đáp, không tạo thêm hai màn hình trùng chức năng. Backend trả candidate_results có cấu trúc từ artifact của tool hợp lệ; frontend hiển thị tên, thứ hạng, điểm, tiêu chí, điểm mạnh và điểm cần làm rõ.

Tên/ID hồ sơ được đối chiếu SQL theo quyền hiện tại; không bóc ID từ lời văn AI để tạo thẻ. Kết quả có thể mở hồ sơ và, với admin, mở trang soạn thư chọn sẵn ứng viên. Mở trang soạn thư chưa gọi AI hoặc gửi thư; người dùng tiếp tục nhập thông tin và tạo nháp.

Khi đọc lại lịch sử, thẻ được lọc lại theo quyền hiện tại. Phần văn bản hội thoại đã lưu không bị xóa hồi tố nếu ứng viên chuyển phòng ban; đây là giới hạn đã được ghi nhận.

### 11.2. Danh sách và hồ sơ ứng viên

1. Thêm danh sách, phân trang và lọc theo tên/email, kỹ năng, kinh nghiệm, phòng ban/vị trí.
2. Giữ filter qua URL để quay lại từ hồ sơ hoặc dùng browser back không mất ngữ cảnh.
3. Hiển thị đầy đủ kỹ năng, kinh nghiệm, học vấn, chứng chỉ, dự án và raw CV text.
4. Thêm ảnh dưới email khi có; ảnh được lấy qua endpoint có xác thực, giữ avatar thay thế khi không có.
5. Bổ sung ảnh ở hồ sơ chi tiết và viewer zoom hỗ trợ bàn phím/mobile.
6. Mở quyền đọc danh sách/chi tiết/ảnh cho tester theo phòng ban, giữ mutation cho admin.

### 11.3. Email, phỏng vấn, intake và quản trị

| Màn hình/nhóm | Chức năng đã có |
| --- | --- |
| /interviews | Chọn ứng viên, sinh câu hỏi có evidence, xem nhóm, sao chép, thay thế/xóa có xác nhận và revision |
| /emails/compose | Chọn người nhận, nhập thông tin phỏng vấn, tạo/sửa nháp, xem trước và duyệt gửi |
| /emails/bulk và /emails/batches | Chuẩn bị nhiều nháp, duyệt và theo dõi từng kết quả trong batch |
| /emails/history | Xem và lọc lịch sử gửi, trạng thái thành công/lỗi/kết quả cần đối soát |
| /ingestion/upload | Chọn phòng ban/vị trí, kéo thả nhiều PDF, theo dõi kết quả riêng từng file |
| /ingestion/jobs | Danh sách/chi tiết tác vụ, trạng thái, lần thử, lỗi và thao tác khôi phục có điều kiện |
| /admin/departments | Tạo, tìm kiếm, phân trang phòng ban, số vị trí/CV và liên kết tra cứu |
| /admin/postings | Tạo và lọc vị trí tuyển dụng theo phòng ban |
| /admin/users | Tạo admin/tester, lọc tài khoản, khóa/mở và thu hồi phiên |
| /ops | Usage, token, chi phí, thiếu dữ liệu, lỗi và các bộ lọc |
| /ops/optimization | Cấu hình active, đề xuất, experiment nền, báo cáo, Approve và rollback |

Gửi email dùng outbox và trạng thái giao nhận để phục hồi khi mạng/queue có lỗi. Trạng thái kết quả chưa rõ cần đối soát, không mặc định gửi lại vì có thể gây thư trùng. Thay đổi nháp/hồ sơ dùng revision hoặc giá trị kỳ vọng ở những thao tác tương ứng để tránh ghi đè dữ liệu mới.

Upload web kiểm tra file ở server, chống trùng theo hash và chọn vị trí rõ ràng. Tải cùng file cho cùng vị trí có thể trả job cũ; khác vị trí gây xung đột để admin kiểm tra/gán lại thay vì âm thầm tạo hồ sơ trùng.

## 12. Những vấn đề đã gặp và cách xử lý

| Vấn đề | Hướng xử lý/kết luận được ghi nhận |
| --- | --- |
| Chi phí Ops không xác định | Rà telemetry embedding và mapping giá; phân biệt thiếu usage, thiếu giá và free tier giá 0 |
| So sánh datetime khi đăng nhập | Chuẩn hóa UTC phù hợp kiểu lưu DB trước khi so expires_at/locked_until |
| Sidebar báo Invalid UUID | Hỗ trợ thread ID lịch sử hợp lệ, không ép tất cả hội thoại cũ thành UUID |
| GET /api/ops/dashboard?days=1/7/30 trả 422 | Điều chỉnh validation query để nhận giá trị truyền qua URL đúng kiểu |
| Nội dung AI hiện nguyên dấu Markdown | Dùng renderer Markdown có kiểm soát và style cho heading/list/table/code |
| Không hiện ảnh chân dung | Bổ sung endpoint/BFF/component ảnh; dữ liệu cần có photo key và MinIO truy cập được |
| Gmail setup failed: RefreshError | Kiểm tra luồng OAuth/token/scopes và xác thực lại khi token không còn dùng được; người dùng báo thử lại đã ổn |
| EXECUTION_INCOMPLETE/409 | Phân biệt trạng thái graph chưa hoàn tất, phục hồi qua GET và tránh tự chạy lại lời gọi AI |
| Login trả 503 | Ghi nhận đã gặp; ý nghĩa là dịch vụ phụ thuộc/backend chưa sẵn sàng. Không đủ log trong bản tổng hợp để khẳng định một nguyên nhân duy nhất |
| Push GitLab treo/xác thực nhầm tài khoản | Kiểm tra remote/credential; người dùng hoàn tất cấu hình xác thực và push thành công |
| Browser test đầu tiên fail trên CI | Assertion chờ chat 5 giây hết hạn, 56 test sau pass; tăng giới hạn CI và pipeline tiếp theo pass |

Với lỗi browser CI, giả thuyết phù hợp log là biên dịch route lần đầu của next dev trên runner. Đã đặt expect 15 giây và test mặc định 60 giây trên CI, giữ local 5/30 giây và không bật retry tự động. Test đầu tiên đã chạy lại pass trên máy; sau đó người dùng xác nhận đủ 4 job xanh và screenshot MR ghi 277 tests.

Cảnh báo hydration về caret-color trong log xuất hiện ở test khác, không phải assertion làm pipeline đó thất bại. Không kết luận mọi cảnh báo đã được sửa chỉ vì pipeline pass.

## 13. Kiểm thử và chuẩn bị bản demo

### 13.1. Các lớp kiểm thử

1. Backend tests kiểm tra nghiệp vụ, xác thực, quyền, schema, state chat, email, intake, prompt và Ops.
2. HTTP integration tests dùng database tạm và provider giả để kiểm tra API qua các luồng thực tế.
3. Playwright chạy trình duyệt với Next/BFF thật và backend mock để kiểm tra đăng nhập, điều hướng, biểu mẫu, lịch sử, phân quyền và phục hồi lỗi.
4. Release checks kiểm tra nhiều route ở desktop/mobile, menu bàn phím, overflow và trang 404.
5. Test toàn luồng kết nối tiếp nhận CV, xử lý, chat/JD, phỏng vấn, email và lịch sử với external I/O giả lập.
6. Kiểm tra Docker/HTTPS trên stack tạm riêng để kiểm chứng kết nối giữa các dịch vụ thật.

### 13.2. Kết quả đã ghi nhận

| Hạng mục | Bằng chứng/kết quả |
| --- | --- |
| Backend trên môi trường Python dự án | 220 passed |
| Backend trong image Linux, network disabled | 220 passed theo báo cáo 28/10 |
| Browser tests | 57 passed theo báo cáo; MR GitLab sau sửa timeout cũng pass |
| Tổng test trên giao diện MR | 277 = 220 backend + 57 browser |
| Lint, TypeScript, production build | Pass trong pipeline frontend-checks |
| Compose config | Pass cho mặc định, demo và demo + scheduler |
| Build Docker backend/frontend | Thành công; sau đó được đưa vào pipeline image |
| Registry | Ảnh người dùng cung cấp có backend và frontend, mỗi mục 1 tag |

Không cộng các lần chạy lặp cùng bộ test thành số lượng test mới. JUnit và trace được giữ làm artifacts của CI trong 7 ngày theo cấu hình hiện tại.

### 13.3. Kiểm tra stack thật và giới hạn bằng chứng

Báo cáo 28/10 ghi nhận đã tạo stack test riêng với MySQL, Redis, Qdrant, MinIO, API, worker, frontend và Caddy. Migration lên 0015, API/FE healthy, worker trả lời ping, HTTPS được xác minh bằng CA của stack và cookie có thuộc tính phù hợp.

Đã dùng hai tester ở hai phòng ban với dữ liệu giả: chỉ thấy CV đúng scope, truy cập hồ sơ/ảnh phòng khác trả 404, email admin trả 403 cho tester, hội thoại riêng không đọc chéo được. Sau khi gộp Compose, có đợt kiểm tra stack riêng nữa; các tài nguyên tạm được dọn.

Các bài test tự động không chứng minh chất lượng extraction/ranking trên mọi CV, quota Gemini thật, OAuth refresh hoặc email đã đến mailbox thật. Người dùng đã báo nhiều đợt test thủ công ổn, nhưng không có một báo cáo benchmark tổng thể chất lượng AI trong phạm vi tài liệu này.

## 14. Docker hóa và thống nhất cấu hình vận hành

### 14.1. Những thay đổi đã chốt

1. Giữ Dockerfile backend ở root, dùng Python 3.12 và PyTorch CPU để tránh tải CUDA không cần thiết.
2. Thêm frontend/Dockerfile riêng, build Next standalone và chạy bằng Node trong runtime image.
3. Chạy ứng dụng trong container bằng user không phải root và chuẩn bị thư mục ghi phù hợp.
4. Bổ sung .dockerignore để loại env/token/credentials, dữ liệu local, CV và thư mục build khỏi context tương ứng.
5. Gộp cấu hình demo vào một docker-compose.yml theo yêu cầu người dùng; không duy trì docker-compose.demo.yml riêng.
6. Dùng .env và .env.example hiện có, bổ sung biến cần thiết thay vì tạo nhiều bộ env trùng nhau.
7. Thêm Caddy, healthcheck, prepare migration/bucket/collection và volume bền.

### 14.2. Các profile

| Chế độ | Dịch vụ/chức năng |
| --- | --- |
| Mặc định | MySQL, Redis, Qdrant, MinIO và minio-init |
| demo | Thêm prepare, API, worker, frontend và proxy HTTPS |
| scheduler | Thêm Beat; prepare cũng được khai báo cho profile này |

API container hiện chạy một worker; Celery sử dụng pool solo trong cấu hình demo. Các cổng dữ liệu mặc định bind localhost, API/FE container giao tiếp nội bộ và Caddy là điểm vào HTTPS.

Checkpoint SQLite local không tự chuyển vào Docker volume. Khi chuyển môi trường phải sao lưu và chuyển checkpoint nhất quán với metadata MySQL; không chạy hai tiến trình ghi chat vào các checkpoint khác nhau nhưng dùng chung metadata mà chưa có thiết kế phối hợp.

### 14.3. Công cụ hỗ trợ demo

- scripts/prepare_demo.py: chuẩn bị bucket/collection sau migration.
- scripts/check_demo.py: đọc và kiểm tra dependency, migration, worker, endpoint; không chứng minh provider key gọi thật thành công.
- scripts/smoke_demo.py: kiểm tra HTTPS, login, cookie, quyền, Origin và logout, không gọi AI/gửi thư.
- docs/deployment/demo.md: hướng dẫn chạy, CA localhost, tài khoản, Gmail, backup và giới hạn.

## 15. Git, GitHub và GitLab CI

### 15.1. Quá trình quản lý nhánh

Các thay đổi đầu được gom ở feature/update. Khi bắt đầu API, dùng feature/fastapi-core làm nhánh tích hợp chính của đợt API/FE. GitHub và GitLab được cấu hình thành hai remote; origin trỏ GitHub, gitlab trỏ GitLab trong quy trình đã dùng.

Đã hướng dẫn kiểm tra git status, chọn đúng file stage, xem diff trước commit, dùng commit ngắn và push từng remote. Thảo luận đổi default branch giúp repository mở đúng nhánh trên giao diện hosting; việc này là thiết lập của từng dịch vụ, không được thay thế chỉ bằng đổi nhánh local.

### 15.2. Bổ sung CI đầu tiên

1. Tạo ci/gitlab-pipeline từ nhánh tích hợp.
2. Kiểm tra Settings → CI/CD → Runners, bật instance runners.
3. Chọn tag saas-linux-small-amd64; runner Windows nhìn thấy ban đầu không dùng cho pipeline này.
4. Tạo .gitlab-ci.yml với backend-tests, frontend-checks, browser-tests và compose-check.
5. Dùng Python 3.12, Node 22, CPU torch và Chromium đúng phiên bản Playwright trong package lock.
6. Dùng .env.example cho kiểm tra Compose; không thêm API key thật vào CI để chạy bộ test mock.
7. Xuất JUnit và browser artifacts; cache npm để giảm tải lại dependency.
8. Cấu hình workflow cho branch/MR, tránh pipeline push trùng khi nhánh đã có MR.

Sau lần browser test fail, sửa timeout CI và push commit mới. Pipeline mới pass 4 job. Tạo MR ci/gitlab-pipeline → feature/fastapi-core, chờ pipeline MR pass rồi merge. GitLab tiếp tục chạy pipeline trên merge commit; code được kéo về máy và push sang GitHub.

### 15.3. Quy trình làm việc đã áp dụng

Tạo nhánh từ bản tích hợp mới nhất → sửa source → kiểm tra → commit → push → kiểm tra pipeline → tạo MR → đọc diff → chờ MR pipeline pass → merge → kiểm tra pipeline sau merge → đồng bộ local/GitHub.

Việc giữ nhánh nguồn sau merge trong các bước vừa làm là lựa chọn tạm thời để dễ theo dõi. Có thể dọn nhánh khi phiên bản đã được kiểm chứng; không cần xóa nhánh để hệ thống hoạt động.

## 16. Build và lưu image trên GitLab Container Registry

### 16.1. Các bước đã hoàn thành

1. Tạo nhánh ci/docker-registry từ feature/fastapi-core đã cập nhật.
2. Mở Deploy → Container Registry và xác nhận tính năng đã bật.
3. Thêm stage images sau verify và browser trong .gitlab-ci.yml.
4. Tạo template .docker-image, dùng Docker 27.5.1 CLI/DinD với TLS và runner Linux.
5. Build backend từ root và frontend từ ./frontend bằng hai Dockerfile hiện có.
6. Gắn tag CI_COMMIT_SHA và label revision; đặt platform linux/amd64.
7. Nhánh phát triển/MR build thử; chỉ khi CI_COMMIT_BRANCH là feature/fastapi-core mới login và push Registry.
8. Dùng CI_REGISTRY_USER/CI_REGISTRY_PASSWORD có sẵn của job, không nhúng thông tin đăng nhập vào Dockerfile.
9. Commit, push, kiểm tra pipeline 6 job, tạo MR ci/docker-registry → feature/fastapi-core và merge.
10. Chờ pipeline sau merge xuất bản image; người dùng đã gửi ảnh Registry có đủ hai repository.

### 16.2. Pipeline hiện tại

| Giai đoạn | Job | Kết quả cần đạt |
| --- | --- | --- |
| verify | backend-tests | 220 tests backend pass |
| verify | frontend-checks | Lint, typecheck và Next production build pass |
| verify | compose-check | Ba cấu hình Compose hợp lệ |
| browser | browser-tests | 57 tests trình duyệt pass; phụ thuộc frontend-checks |
| images | backend-image | Build thành công, push khi đúng nhánh tích hợp |
| images | frontend-image | Build thành công, push khi đúng nhánh tích hợp |

Các job image đợi các giai đoạn trước thành công. Hai job image độc lập nên trong trường hợp một job push thành công và job kia fail, cần chờ/khôi phục đủ cặp image trước khi triển khai; Registry không tạo một giao dịch nguyên tử cho cả cặp.

### 16.3. Đầu ra và ý nghĩa

Hai đường dẫn repository:

```text
registry.gitlab.com/sangot2004/cv-rag-ai/backend:<commit-sha>
registry.gitlab.com/sangot2004/cv-rag-ai/frontend:<commit-sha>
```

Ảnh Registry xác nhận mỗi repository có một tag nhưng không hiển thị nội dung tag. Trước khi triển khai cần mở chi tiết để chọn đúng cặp cùng commit. Source local hiện ở merge commit 49304b4; không tự suy rằng mọi tag đang có đều tương ứng commit đó khi chưa đọc chi tiết Registry.

Đến đây đã có CI, kiểm chứng Docker build và xuất bản image. Chưa có CD triển khai máy chủ. Compose hiện vẫn tham chiếu image demo/build local; cần nối các image Registry vào cấu hình trước khi dùng cho triển khai từ image đã phát hành.

## 17. Các mốc Git tiêu biểu và vị trí source

### 17.1. Mốc commit

| Commit | Nội dung mốc |
| --- | --- |
| c7e4bc9 | Khởi tạo project và ingestion pipeline |
| 507c97a | Parsing, extraction, chunking và indexing Gemini |
| 9114c0b | Reranker, agent tools và query interface |
| 477b013 | OCR fallback, JD matching và Top-K |
| 01091ae | Lịch sử chat |
| 4e747a6 | Phạm vi phòng ban |
| beebe7a | Workflow thư mời phỏng vấn |
| c957d9b | Sinh câu hỏi phỏng vấn dựa trên CV |
| bd99634 | Đề xuất tối ưu và paired experiments |
| 1bef4f5 | Auth, LangSmith prompts và Ops safeguards |
| 484db52 | FastAPI chat có xác thực và JD confirmation bền |
| 244051e | Kế hoạch FE và prototype auth/chat |
| 29d6a43 | Frontend tuyển dụng, quản trị và tiếp nhận CV |
| cdf9a83 | System Ops và cải thiện giao diện |
| 17585cb | Hoàn thiện UI và Docker setup |
| 58b6074 / 683e620 | GitLab CI và điều chỉnh timeout browser tests |
| 413c545 | Merge nhánh GitLab CI vào feature/fastapi-core |
| 94926d0 / 49304b4 | Build/publish Docker images và merge nhánh Registry |

Đây là các mốc tiêu biểu đọc từ lịch sử Git hiện tại, không phải danh sách mọi commit hoặc mọi thao tác thủ công.

### 17.2. Bản đồ thư mục

| Đường dẫn | Nội dung |
| --- | --- |
| app.py | Giao diện Streamlit giai đoạn đầu |
| main.py, src/api/ | Entrypoint và API FastAPI |
| src/auth/, src/chat/ | Phiên, quyền, hội thoại, confirmation và adapter kết quả |
| src/agent/, src/retrieval/ | Agent, tools, truy vấn, xếp hạng và scope |
| src/ingestion/, src/storage/, src/workers/ | Pipeline CV, storage và tác vụ nền |
| src/candidates/, src/management/ | Hồ sơ, ảnh, phòng ban, vị trí và tài khoản |
| src/interview/, src/notification/ | Câu hỏi phỏng vấn và thư mời |
| src/llm/, src/ops/ | Prompt, key manager, usage và tối ưu |
| src/db/, alembic/ | ORM và lịch sử schema; revision source hiện tại đến 0015 |
| frontend/src/app/ | Routes web và Next BFF |
| frontend/src/features/ | Các module giao diện theo nghiệp vụ |
| frontend/src/components/, frontend/src/lib/ | UI chung, contracts, client API và backend adapter |
| design/ | Screen/HTML và tài liệu prototype |
| tests/, frontend/tests/ | Backend/API tests và Playwright/mock backend |
| deploy/demo/, scripts/ | Caddy và các công cụ quản trị/kiểm tra |
| docs/ | API, FE, triển khai, kiểm thử và báo cáo tổng hợp |
| .gitlab-ci.yml | Quy trình kiểm thử/build/publish trên GitLab |

## 18. Những việc tiếp theo và điều kiện hoàn thành

### 18.1. Thứ tự triển khai tiếp đã thống nhất

1. Chốt môi trường: VPS/server hay thử image Registry trên máy trước; xác định hệ điều hành, kiến trúc CPU và domain.
2. Chọn đúng cặp backend/frontend có cùng tag commit hoặc digest đã kiểm chứng.
3. Chỉnh Compose để dùng image Registry theo cấu hình; giữ một docker-compose.yml, bảo toàn cách chạy phát triển hiện có.
4. Cấp quyền kéo image cho máy đích nếu Registry yêu cầu xác thực.
5. Chuẩn bị biến môi trường, volume, cấu hình AI/LangSmith và OAuth Gmail nếu dùng email.
6. Sao lưu/chuyển dữ liệu MySQL, MinIO, Qdrant và checkpoint nhất quán nếu mang dữ liệu từ môi trường cũ.
7. Trỏ domain, cấu hình HTTPS và khởi động stack; xác nhận prepare/migration, API/FE healthy và worker hoạt động.
8. Chạy readiness/smoke, sau đó nghiệm thu với CV mẫu và provider thật được phép sử dụng.
9. Bổ sung job deploy thủ công sau khi quy trình triển khai trên máy chủ ổn định; chuẩn bị backup và rollback phù hợp schema.

### 18.2. Giới hạn còn cần giữ rõ

- Chưa có bằng chứng triển khai public; trạng thái máy chủ, domain và cấu hình vận hành còn cần chốt.
- Chat hiện phụ thuộc một tiến trình API ghi checkpoint; muốn scale nhiều instance cần thiết kế coordination và storage phù hợp.
- Không có cam kết exactly-once cho mọi thao tác chat/provider; các trạng thái kết quả chưa rõ phải được phục hồi có kiểm soát.
- Ops experiment chưa bao phủ retrieval, LLM judge, routing độ khó hay đo trực tiếp lợi ích cache.
- Giá 0 của free tier không chứng minh khoản tiền tiết kiệm; log usage có thể thiếu do provider hoặc lỗi ghi telemetry.
- Một số dependencies Python và service image còn dùng version range/tag thay đổi; build lại cùng source có thể lấy dependency khác.
- Model ranking cần nghiệm thu trên dữ liệu có đáp án chuẩn; điểm AI hỗ trợ người tuyển dụng, không tự thay quyết định tuyển dụng.
- Cleanup policy Registry chưa được lên lịch theo ảnh hiện tại; có thể cấu hình sau khi chốt cách giữ các phiên bản phục vụ rollback.

Đầu ra cần đạt ở giai đoạn kế tiếp là một URL HTTPS hoạt động, đăng nhập được, xử lý CV/chat/email theo quyền và có cách cập nhật/khôi phục rõ ràng. Hai image trên Registry là đầu vào cho giai đoạn đó.

## 19. Phụ lục — lệnh tham khảo và tài liệu gốc

### 19.1. Kiểm tra phiên bản source

```bash
git status --short --branch
git log -1 --oneline
git remote -v
```

Sau khi merge trên GitLab, quy trình đồng bộ đã dùng:

```bash
git switch feature/fastapi-core
git pull --ff-only gitlab feature/fastapi-core
git push origin feature/fastapi-core
```

### 19.2. Chạy môi trường phát triển

Tại root, chạy dịch vụ dữ liệu và áp dụng migration khi đã chuẩn bị cấu hình/backup phù hợp:

```bash
docker compose up -d
PYTHONPATH=. .venv/bin/alembic upgrade head
PYTHONPATH=. .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
```

Terminal khác tại root:

```bash
PYTHONPATH=. .venv/bin/celery -A src.workers.celery_app worker --pool=solo --loglevel=info
```

Terminal frontend:

```bash
cd frontend
npm ci
npm run dev
```

Các lệnh trên là tham khảo cách chạy đã có, không phải lệnh deploy image Registry. Không khởi động thêm API/Streamlit cùng ghi checkpoint nếu đã có instance đang chạy.

### 19.3. Chạy các kiểm tra chính

```bash
LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false .venv/bin/python -m pytest -q
APP_ENV_FILE=.env.example docker compose --env-file .env.example --profile demo --profile scheduler config --quiet
```

Trong frontend/:

```bash
npm run lint
npm run typecheck
npm run build
PLAYWRIGHT_CHANNEL=chromium npm run test:e2e
```

Lệnh browser cần Chromium của Playwright được cài; CI thực hiện bằng npx playwright install --with-deps chromium. Không cần chạy lại toàn bộ test chỉ để đọc tài liệu này.

### 19.4. Tài liệu đối chiếu trong repository

- README.md: tổng quan, pipeline và hướng dẫn nền tảng.
- AUTH_SETUP.md: lịch sử thiết kế auth và test tài khoản.
- OPS_SETUP.md: telemetry, pricing và giới hạn Ops.
- docs/api/setup.md, implementation-plan.md, contract.md: API và hướng dẫn thử.
- docs/api/candidates.md, chat-candidate-results.md, interviews.md: ứng viên, thẻ JD/Top-K và phỏng vấn.
- docs/api/emails.md, administration-ingestion.md: thư mời, quản trị và intake.
- docs/api/ops-monitoring.md, ops-optimization.md: dashboard và experiment.
- docs/frontend/FE_IMPLEMENTATION_PLAN.md: kế hoạch FE cùng các cập nhật phạm vi.
- docs/testing/release-checklist.md, release-report-2026-10-28.md: nghiệm thu và bằng chứng kiểm thử.
- docs/testing/gitlab-ci.md: hướng dẫn CI ban đầu.
- docs/deployment/demo.md: vận hành Compose/HTTPS và dữ liệu.
- .gitlab-ci.yml, Dockerfile, frontend/Dockerfile, docker-compose.yml: cấu hình đang dùng.

Một số tài liệu đầu kỳ còn mô tả trạng thái cũ, ví dụ danh sách ứng viên chỉ cho admin hoặc một module chưa có API. Báo cáo này ưu tiên source hiện tại và phần cập nhật phạm vi mới hơn: tester hiện được đọc hồ sơ trong phòng ban; các API quản trị, email và Ops đã có. Số migration hoặc tình trạng worker trong báo cáo 28/10 chỉ là snapshot của lần kiểm tra đó, không được coi là trạng thái môi trường đang chạy ngày 30/10.

Tài liệu không chứa khóa API, token OAuth, mật khẩu hay nội dung CV thật. Các tài liệu đính kèm được nhắc tới từ đầu hội thoại là bối cảnh đầu vào; bản tổng hợp này dựa trên phần trao đổi được cung cấp và các nguồn trong repository đã đọc lại.
