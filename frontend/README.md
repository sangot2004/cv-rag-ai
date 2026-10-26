# CV RAG AI — Frontend

Next.js App Router + TypeScript, giao diện theo bản F1 đã duyệt trong `design/`.

## Phạm vi đã triển khai

- Đăng nhập, cookie HttpOnly, xác minh phiên, đăng xuất và thông báo hết phiên.
- Sidebar theo tài khoản, danh sách tối đa 50 hội thoại, tìm trong danh sách đã tải.
- Đọc tiếp hội thoại cũ có ID dạng tên (ví dụ `test-cart`), cùng với hội thoại UUID mới.
- Tạo hội thoại khi gửi câu hỏi đầu tiên; đọc lại lịch sử qua URL `chat?thread=...`.
- Gửi câu hỏi, chỉnh/xác nhận/hủy JD theo đúng confirmation ID, nhiều xác nhận cùng lúc.
- Feedback append, xóa hội thoại, thử dọn lại khi backend báo cleanup pending.
- Khóa gửi khi đang chạy, chờ xác nhận, trạng thái không chắc chắn hoặc execution incomplete.
- Giao diện desktop/mobile, drawer và hộp thoại xóa dùng native dialog.
- Trang `/forbidden`; quyền dữ liệu và thao tác luôn do FastAPI kiểm tra.
- Danh sách và chi tiết ứng viên cho admin, tìm kiếm/lọc/phân trang, giữ bộ lọc qua URL.

Các trang quản trị, ứng viên, email, ingestion và Ops sẽ nối sau khi có API tương ứng.

## Chạy local

Node.js >= 20.9; môi trường đã kiểm tra: Node 22.17.1, npm 10.9.2.

Từ thư mục `frontend/`:

```bash
npm ci
```

Tạo `.env.local` nếu chưa có, với nội dung:

```dotenv
API_INTERNAL_URL=http://127.0.0.1:8000
```

Giữ Gemini/LangSmith/database secrets trong `.env` của backend. FE chỉ gọi FastAPI.

Terminal backend, từ gốc repository:

```bash
source .venv/bin/activate
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
```

Dùng các dịch vụ backend đã cấu hình. Không chạy Streamlit cùng ghi checkpoint với API.

Terminal frontend, trong `frontend/`:

```bash
npm run dev
```

Mở <http://localhost:3000>. Đăng nhập bằng tài khoản đã tạo qua `manage_users.py`.
Frontend mặc định đi qua Next server → `API_INTERNAL_URL`; không cần gọi FastAPI trực tiếp từ browser.

## Cấu trúc

```text
src/app/                 Routes và layout
  api/session/           Login, me, logout; cookie HttpOnly
  api/backend/[...path]/ Proxy chỉ cho phép các endpoint hội thoại hiện có
  login/                 Form đăng nhập
  chat/                  Không gian hội thoại
  forbidden/             Thông báo không có quyền
src/components/          Provider và thành phần UI dùng chung
src/features/auth/       Login và xác minh phiên
src/features/chat/       Sidebar, chat, tiêu chí JD
src/lib/                 Hợp đồng dữ liệu, HTTP client, server transport
tests/                   Backend giả lập + test trình duyệt
```

## Phiên và bảo vệ dữ liệu

- Token backend chỉ nằm trong cookie HttpOnly; không trả trong JSON login, không dùng localStorage/sessionStorage.
- Cookie SameSite=Lax, Path=/, hạn dùng không vượt thời hạn backend trả về.
- Production dùng cookie Secure với tên `__Host-cv_session`, cần HTTPS.
- Mutation yêu cầu Origin cùng origin FE; nếu đứng sau reverse proxy, đặt `APP_ORIGIN` bằng origin public chính xác (ví dụ `https://cv.example.com`, không có slash cuối).
- `API_INTERNAL_URL` là origin cố định phía server; proxy allowlist các method/path, không forward URL tùy ý hoặc cookie browser.
- Dữ liệu riêng dùng no-store; cache trong React Query được phân theo user/thread và dọn khi đổi tài khoản/đăng xuất.
- Kiểm tra phiên khi vào trang, quay lại tab và mỗi 60 giây. Các tab cùng origin nhận thông báo khi phiên thay đổi.
- Logout lỗi kết nối vẫn giữ cookie để có thể thử thu hồi phiên backend lại; không báo thành công giả.
- Không retry mutation tự động. Sau timeout/mất mạng, dùng GET kiểm tra trạng thái; thao tác đó không gọi lại model.

## Kiểm tra

```bash
npm run lint
npm run typecheck
npm run build
npm run test:e2e
```

Test trình duyệt mặc định dùng Google Chrome đã cài. Nếu dùng Chromium của Playwright:

```bash
npx playwright install chromium
PLAYWRIGHT_CHANNEL=chromium npm run test:e2e
```

Playwright tự mở backend giả lập cổng 28101 và Next cổng 28100, tự đóng khi xong.
Hai cổng phải trống. Dữ liệu test là giả; không đọc database, gọi Gemini hoặc dùng tài khoản thật.
`API_INTERNAL_URL` trong test được trỏ riêng đến backend giả lập.

Kết quả kiểm tra 21/10/2026 sau INT-01: toàn bộ 31 test trình duyệt pass (15 auth/chat, 9 ứng viên, 7 phỏng vấn). ESLint, TypeScript và production build pass. Test trình duyệt dùng API giả lập; 88 test API/generator pass bằng SQLite/model/MinIO giả lập; test rollback transaction bổ sung cũng pass (tổng 89 ca đã kiểm tra).

Các test kiểm chứng BFF thực, cookie/Origin, lỗi đăng nhập/đăng xuất, revocation,
lịch sử và ownership hai tài khoản, feedback, xóa/cleanup, JD nhiều interrupt,
zero/null/Top-K, stale confirmation, timeout và giao diện mobile.
Bao gồm hồi quy admin mở/chat/xóa hội thoại cũ không dùng UUID và thông báo lỗi
dễ hiểu khi dữ liệu phản hồi không hợp lệ.
Ảnh kiểm tra được lưu dưới `test-results/preview-*.png` (Git ignore).

## Test thủ công với backend thật

1. Đăng nhập admin/tester, tải lại trang: vẫn đúng tài khoản.
2. Gửi câu hỏi về CV đã có, mở lại hội thoại và kiểm tra lịch sử.
3. Dán JD, sửa Top-K/kinh nghiệm, xác nhận hoặc hủy.
4. Đánh giá câu trả lời, xóa hội thoại và tải lại danh sách.
5. Dùng hai profile trình duyệt kiểm tra lịch sử riêng và phạm vi phòng ban.
6. Đăng xuất; tải lại `/chat` phải trở về đăng nhập.

## Giới hạn hiện tại

- Chat đồng bộ, chưa streaming. Timeout BFF là 120 giây; timeout trình duyệt/proxy không chứng minh graph đã dừng.
- Draft và trạng thái đã bấm feedback chỉ giữ trong bộ nhớ trang. Reload mất draft; API chưa có endpoint đọc feedback nên không hiển thị lịch sử vote.
- Danh sách chỉ 50 hội thoại mới nhất theo API; chưa phân trang hoặc tìm toàn bộ lịch sử.
- Kết quả chat được render dạng văn bản an toàn, chưa có bảng ứng viên/Markdown tương tác.
- Test tự động dùng backend giả lập: cần test thủ công với MySQL và Gemini thật để xác nhận toàn bộ hệ thống.
- `npm audit --omit=dev` không ghi nhận lỗ hổng ở lần kiểm tra 2026-10-19. Full audit còn 5 cảnh báo high trong chuỗi ESLint → fast-glob → micromatch → braces; npm đề xuất hạ ESLint config về Next 14, không phù hợp Next 16. Theo dõi bản vá tooling trước khi nâng cấp.

## Build/deploy

`npm run build` tạo bản production; `npm start` chạy server. BFF yêu cầu Node server,
không dùng static export. Cấu hình HTTPS, `APP_ORIGIN`, backend origin và timeout proxy
phù hợp trước khi triển khai. Commit `package-lock.json`; bỏ qua `.env.local`,
`node_modules`, `.next*`, `test-results`.


## Giao diện ứng viên (CAND-01, CAND-02)

Admin vào mục **Ứng viên** từ sidebar chat hoặc mở `/candidates`.
Backend cần có hai API trong [contract ứng viên](../docs/api/candidates.md).

- Tìm tên/email, vị trí ứng tuyển; lọc đồng thời nhiều kỹ năng bằng dấu phẩy,
  khoảng kinh nghiệm (giá trị 0 hợp lệ), sắp xếp và phân trang.
- Bấm tên phòng ban/vị trí tuyển dụng ở bảng hoặc hồ sơ để lọc nhóm tương ứng.
  API chưa cung cấp danh mục đầy đủ cho dropdown phòng ban/vị trí.
- Bấm tên ứng viên để xem liên hệ, kỹ năng, kinh nghiệm, học vấn, chứng chỉ,
  dự án và nội dung CV đã trích xuất. Danh sách hiển thị chân dung dưới email nếu có ảnh đã lưu trong MinIO; lỗi tải ảnh thì ẩn. Hồ sơ chi tiết có ảnh ở đầu trang; bấm ảnh trong danh sách hoặc hồ sơ để mở lớn, dùng nút +/− zoom 100–300%, đặt lại, cuộn để xem, đóng bằng nút/Esc hoặc bấm ngoài. Ảnh lỗi trong hồ sơ dùng avatar chữ cái. Chưa có xem/tải PDF.
- Quay lại danh sách, tải lại hoặc Back trên trình duyệt giữ bộ lọc và số trang trong URL.
- Tester không có mục ứng viên; mở URL trực tiếp hiển thị thiếu quyền, API trả 403.
- BFF chỉ cho phép GET danh sách/chi tiết; dùng cookie phiên hiện có.
  Dữ liệu không lưu localStorage; cache truy vấn gắn với tài khoản.

Kiểm tra thủ công với dữ liệu thật:

1. Chạy FastAPI ở cổng 8000, chạy `npm run dev` trong `frontend`, đăng nhập admin.
2. Vào **Ứng viên**, tìm tên/email đã có. Bấm **Áp dụng bộ lọc** và kiểm tra kết quả.
3. Nhập kỹ năng có trong CV, thử kinh nghiệm tối thiểu 0; thử khoảng tối thiểu lớn hơn tối đa để xem lỗi.
4. Mở hồ sơ, đối chiếu dữ liệu CV, quay lại và kiểm tra bộ lọc được giữ.
5. Bấm phòng ban/vị trí trên bảng để lọc; bỏ nhóm bằng nút có dấu ×.
6. Nếu đủ dữ liệu, chuyển trang; thử màn hình điện thoại và điều hướng Hỏi đáp AI.
7. Dùng tester mở trực tiếp `/candidates` và một URL hồ sơ: phải báo thiếu quyền.

`tests/candidates.spec.ts` kiểm chứng các luồng trên bằng API giả lập, bao gồm
truyền nhiều kỹ năng qua BFF, lỗi 403/404/503, dữ liệu sai định dạng, phiên bị thu hồi,
render nội dung CV an toàn và bố cục mobile. Ảnh nằm trong `test-results/candidate*.png`.


Sau khi bổ sung ảnh hồ sơ và zoom: 9 test ứng viên đều đã pass (trường hợp avatar dự phòng được chạy lại sau khi sửa selector để bỏ qua biểu tượng Next.js). Lint, TypeScript và production build pass.

Ảnh chân dung dùng `has_photo` trong response danh sách/chi tiết và endpoint
`GET /api/candidates/{candidate_id}/photo`. Khi cập nhật FE cần restart FastAPI
để có schema/endpoint mới. Ảnh đi qua BFF có cookie phiên, không dùng public bucket
hoặc đưa bearer token vào URL. Test ảnh nằm trong `tests/candidates.spec.ts`.


## Câu hỏi phỏng vấn (INT-01)

- Admin mở hồ sơ → **Tạo câu hỏi phỏng vấn**, hoặc vào menu **Câu hỏi phỏng vấn** (`/interviews`).
- Tìm/chọn ứng viên theo tên/email, chọn số câu 3–15, sinh và đọc lại bộ đã lưu.
- Lọc Kỹ thuật/Thiết kế hệ thống/Kỹ năng mềm; mỗi câu có section và trích dẫn CV, nút sao chép.
- Sinh lại/xóa có xác nhận; dùng revision của bộ để tránh ghi đè từ tab cũ.
- Lỗi provider/evidence không hợp lệ giữ bộ cũ; sau timeout FE GET lại trạng thái, không tự gửi lại.
- Tester không có menu hoặc quyền API. CV chưa có raw_text thì khóa nút sinh.
- Số câu hợp lệ thực tế có thể ít hơn số yêu cầu. Chưa có JD, độ khó/tỷ lệ nhóm,
  Green/Red Flags, chỉnh sửa/ghi chú, xuất PDF/Word.

Khởi động lại FastAPI để có nhóm **interviews** trong Swagger. Chạy API một worker;
Gemini và prompt LangSmith hiện có cần sẵn sàng để sinh với CV thật.
[Contract và cách test API](../docs/api/interviews.md).

`tests/interviews.spec.ts` dùng API mô phỏng để kiểm tra toàn luồng, xác nhận,
revision, lỗi provider/timeout, quyền và mobile. Ảnh: `test-results/interviews-*.png`.


## Thư mời, hàng loạt và lịch sử (MAIL-01/02/03/04)

Admin có menu **Soạn thư mời**, **Gửi hàng loạt**, **Lịch sử gửi thư**.
Hồ sơ và trang câu hỏi phỏng vấn có nút **Soạn thư mời**.

1. Tạo nháp: chọn ứng viên (bulk tối đa 20), nhập vị trí/ngày/giờ/link hoặc địa điểm.
2. Soạn thủ công hoặc tạo nháp AI, sửa và **Lưu bản nháp**, xem trước.
3. Bulk chọn riêng các nháp hợp lệ đã lưu; kiểm tra popup tên/email/subject rồi xác nhận.
4. Màn batch hiển thị queued/sending/success/failed/unknown. Lịch sử mở nội dung thực đã duyệt.
5. Reload/đăng nhập lại: mở **Đợt gửi & bản nháp** để tiếp tục hoặc xem tiến độ.

Lưu nháp không gửi. Nháp đang sửa chưa lưu không được tính vào danh sách duyệt.
Cần xác nhận riêng nếu người nhận từng được mời; thư đang chờ/chưa rõ kết quả chặn gửi trùng.
Với kết quả unknown, **Kiểm tra Gmail** chỉ đối chiếu Sent và không gửi lại.

Cần migration `0013`, MySQL/Redis, FastAPI, Celery worker code mới và Gmail OAuth.
Cách chạy worker, contract, kiểm tra thật và giới hạn: [docs/api/emails.md](../docs/api/emails.md).
Màn email plain text, chưa có attachment/rich HTML, export hay nhắc hẹn.

Kiểm tra hoàn tất 21/10/2026: **101 test backend**, **38 test trình duyệt**, lint,
TypeScript và production build pass. Test dùng Gmail/model giả lập, chưa gửi email thật.
Migration đã kiểm tra up/down giữ log legacy và sinh SQL MySQL.

## Quản trị và tiếp nhận CV (ADM-01/02/03, ING-01/02/03)

Admin có các menu mới **Phòng ban**, **Vị trí tuyển dụng**, **Quản lý tài khoản**,
**Upload CV**, **Theo dõi xử lý**. Trong hồ sơ ứng viên có form gán/đổi/bỏ vị trí.
Từ chat có liên kết **Tiếp nhận CV** và **Quản trị**.

1. Tạo phòng ban và vị trí tuyển dụng.
2. Tạo tester và gán phòng ban; khóa/mở thu hồi phiên nhưng giữ hội thoại.
3. Upload PDF vào vị trí đã chọn; mỗi file trả tác vụ riêng, không báo đã index sớm.
4. Mở tác vụ xem kết quả, lỗi an toàn, thử lại có xác nhận và mở hồ sơ sau hoàn tất.
5. Gán lại CV hiện có để áp dụng phạm vi phòng ban tương ứng khi tra cứu.

Cần migration `0014` và khởi động lại FastAPI/worker. Quy tắc file, HTTP contract,
cách chạy và test thủ công: [administration-ingestion.md](../docs/api/administration-ingestion.md).

Test trình duyệt mới:

```bash
npm run test:e2e -- tests/management-ingestion.spec.ts
```

Test đi qua BFF thật với backend giả lập; kiểm tra quyền, session bị thu hồi,
upload nhiều file/lỗi riêng, khôi phục queue, gán vị trí và mobile. Các test backend
dùng PDF trong bộ nhớ, database tạm và model/storage giả lập; không gọi AI thật.

## System Ops

Admin mở `/ops` để xem usage, chi phí, biểu đồ, cảnh báo và log. Không cần migration mới.
Xem [contract và hướng dẫn test](../docs/api/ops-monitoring.md). Optimization/experiment có tại `/ops/optimization`; xem [hướng dẫn migration/worker](../docs/api/ops-optimization.md).
