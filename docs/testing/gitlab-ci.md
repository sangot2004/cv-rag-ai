# GitLab CI

Pipeline được khai báo trong `.gitlab-ci.yml`, chạy trên instance runner Linux
`saas-linux-small-amd64`. Bật instance runners trong Settings → CI/CD → Runners.
Không cần tạo project runner riêng.

## Các job

| Job | Kiểm tra | Thành công khi |
| --- | --- | --- |
| `backend-tests` | Toàn bộ pytest, dùng Python 3.12 và PyTorch CPU | Tất cả test pass |
| `frontend-checks` | `npm ci`, lint, typecheck, production build | Cả ba bước kiểm tra pass |
| `browser-tests` | Playwright Chromium với mock backend | Tất cả browser test pass |
| `compose-check` | Cấu hình Compose mặc định, demo, demo + scheduler | Cả ba cấu hình hợp lệ |

Các job verify chạy độc lập. Browser tests bắt đầu sau khi frontend checks pass.
Browser tests dùng `next dev`, nên lần đầu truy cập mỗi trang có thể phải chờ
biên dịch. Trên CI, assertion chờ tối đa 15 giây và mỗi test tối đa 60 giây
(local vẫn là 5 và 30 giây). Các test có timeout riêng giữ nguyên cấu hình đó.
Không bật retry tự động; test vẫn phải đạt các assertion hiện có.
Pipeline chạy khi push nhánh, tạo/cập nhật merge request hoặc chạy thủ công trên
nhánh. Nếu nhánh đã có merge request, push chỉ tạo pipeline merge request để tránh
chạy trùng. Tag không kích hoạt pipeline này.

Backend và browser tests dùng dữ liệu/provider giả lập. Không cần CI variables
chứa Gemini, LangSmith, Gmail, mật khẩu database hay `.env` thật. Compose dùng
`.env.example`, chỉ kiểm tra cấu hình và không khởi động container.

Pipeline này chưa build/push Docker image và chưa deploy ứng dụng. Compose hợp lệ
không thay thế việc test Docker stack hoặc provider thật trong release checklist.

## Chạy lần đầu

Tại thư mục gốc, kiểm tra các thay đổi rồi commit riêng cấu hình CI:

```sh
git status
git add .gitlab-ci.yml docs/testing/gitlab-ci.md
git diff --cached --check
git diff --cached --stat
git commit -m "ci: add GitLab pipeline"
git push -u gitlab ci/gitlab-pipeline
```

Vào GitLab → Build → Pipelines, mở pipeline của commit vừa push.
Mong đợi cả bốn job màu xanh và trạng thái pipeline là **Passed**.
JUnit của backend và Playwright xuất hiện trong phần Tests. Job artifacts giữ
báo cáo trong 7 ngày; Playwright giữ trace khi test thất bại.

Sau khi pipeline pass, tạo merge request từ `ci/gitlab-pipeline` vào
`feature/fastapi-core`. Kiểm tra diff và pipeline merge request trước khi merge.
Muốn lưu nhánh trên GitHub nữa: `git push -u origin ci/gitlab-pipeline`.

## Khi gặp lỗi

- **Pending:** kiểm tra instance runners đang bật và runner hỗ trợ tag Linux trên.
  Kiểm tra thông báo hạn mức compute/xác minh tài khoản của GitLab nếu có.
- **Cài dependency thất bại:** xem dòng lỗi đầu tiên trong job. Python hiện dùng
  version range trong `requirements.txt`; Node dùng version khóa trong
  `package-lock.json`. Lần đầu tải PyTorch và Chromium có thể mất vài phút.
- **Browser test thất bại:** tải artifact `frontend/test-results/`, mở trace bằng
  `npx playwright show-trace <đường-dẫn-trace.zip>` từ thư mục frontend.
- **Compose thất bại:** giữ `APP_ENV_FILE=.env.example`; chỉ truyền `--env-file`
  chưa thay thế đường dẫn `env_file` của các service trong Compose.

Không cần bật Auto DevOps cho pipeline này. Không thêm token hoặc dữ liệu CV thật
vào artifacts.

Tham khảo: [GitLab workflow rules](https://docs.gitlab.com/ci/yaml/workflow/),
[Playwright trên CI](https://playwright.dev/docs/ci).
