import { expect, test, type Page } from "@playwright/test";
const backend = "http://127.0.0.1:28101", origin = "http://127.0.0.1:28100";
const engineering = "11111111-1111-4111-8111-111111111111", sales = "11111111-1111-4111-8111-222222222222", posting = "22222222-2222-4222-8222-222222222222";
const cv = (name = "NguyenVanA_DataEngineer_CV.pdf", marker = "a") => ({name, mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7\n" + marker.repeat(22000))});
async function login(page: Page, username = "sang") {
  await page.goto("/login"); await page.getByLabel("Tên đăng nhập", {exact: true}).fill(username);
  await page.getByLabel("Mật khẩu", {exact: true}).fill("test-password-123");
  await page.getByRole("button", {name: "Đăng nhập", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Bắt đầu từ một câu hỏi"})).toBeVisible();
}
async function setupUpload(page: Page) {
  await page.goto("/ingestion/upload");
  await page.getByLabel("Phòng ban tiếp nhận", {exact: true}).selectOption(engineering);
  await page.getByLabel("Vị trí tiếp nhận", {exact: true}).selectOption(posting);
}
test.beforeEach(async ({request}) => {await request.post(`${backend}/control/reset`);});

test("departments and postings create, filter and link to candidate scope", async ({page}) => {
  await page.setViewportSize({width: 1440, height: 1000}); await login(page);
  await page.getByRole("link", {name: "Quản trị", exact: true}).click();
  await page.getByLabel("Tên phòng ban", {exact: true}).fill("Product");
  await page.getByRole("button", {name: "Tạo mới", exact: true}).click();
  await expect(page.getByRole("status")).toContainText("Đã tạo thành công.");
  const row = page.getByRole("row").filter({has: page.getByText("Product", {exact: true})});
  await row.getByRole("link", {name: "Xem vị trí", exact: true}).click();
  await expect(page).toHaveURL(/\/admin\/postings\?department_id=/);
  await page.getByLabel("Tên vị trí tuyển dụng", {exact: true}).fill("Product Engineer");
  await page.getByRole("button", {name: "Tạo mới", exact: true}).click();
  await expect(page.getByRole("row").filter({has: page.getByText("Product Engineer", {exact: true})})).toBeVisible();
  await page.screenshot({path: "test-results/admin-postings-desktop.png"});
  await page.getByRole("link", {name: "Xem ứng viên", exact: true}).click();
  await expect(page).toHaveURL(/\/candidates\?posting_id=/);
});

test("account password clears, lock confirmation revokes tester session and reopening preserves access", async ({page, browser, request}) => {
  await login(page); await page.goto("/admin/users");
  await page.getByLabel("Tên tài khoản mới", {exact: true}).fill("tester_new");
  await page.getByLabel("Mật khẩu mới", {exact: true}).fill("test-password-123");
  await page.getByLabel("Phòng ban của tài khoản", {exact: true}).selectOption(engineering);
  await page.getByRole("button", {name: "Tạo mới", exact: true}).click();
  await expect(page.getByLabel("Mật khẩu mới", {exact: true})).toHaveValue("");
  const row = page.getByRole("row").filter({has: page.getByText("tester_new", {exact: true})});
  await expect(row).toBeVisible();
  const other = await browser.newContext(); const tester = await other.newPage(); await login(tester, "tester_new");
  await row.getByRole("button", {name: "Khóa tài khoản", exact: true}).click();
  await page.getByRole("dialog", {name: "Khóa tài khoản?", exact: true}).getByRole("button", {name: "Hủy", exact: true}).click();
  let calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.filter((c: {path: string}) => c.path.endsWith("/active"))).toHaveLength(0);
  await row.getByRole("button", {name: "Khóa tài khoản", exact: true}).click();
  await page.getByRole("dialog", {name: "Khóa tài khoản?", exact: true}).getByRole("button", {name: "Xác nhận", exact: true}).click();
  await expect(row.getByText("Đã khóa", {exact: true})).toBeVisible();
  await tester.reload(); await expect(tester).toHaveURL(/\/login\?reason=expired/);
  await row.getByRole("button", {name: "Mở tài khoản", exact: true}).click();
  await page.getByRole("dialog", {name: "Mở lại tài khoản?", exact: true}).getByRole("button", {name: "Xác nhận", exact: true}).click();
  await expect(row.getByText("Đang hoạt động", {exact: true})).toBeVisible();
  await login(tester, "tester_new");
  calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(JSON.stringify(calls)).not.toContain("test-password-123");
  await page.screenshot({path: "test-results/admin-users-desktop.png"}); await other.close();
});

test("multiple uploads keep separate results, completion comes from job polling, and file replay reuses job", async ({page, request}) => {
  await login(page); await setupUpload(page);
  await page.getByLabel("File CV", {exact: true}).setInputFiles([cv(), cv("Invalid_Name.pdf", "b")]);
  await page.getByRole("button", {name: "Upload 2 CV", exact: true}).click();
  await expect(page.getByRole("article", {name: "File NguyenVanA_DataEngineer_CV.pdf", exact: true})).toContainText("Đã tiếp nhận file.");
  await expect(page.getByRole("article", {name: "File Invalid_Name.pdf", exact: true})).toContainText("INVALID_FILENAME_FORMAT");
  await page.screenshot({path: "test-results/ingestion-upload-desktop.png"});
  await page.getByRole("link", {name: "Xem tác vụ", exact: true}).click();
  await expect(page.getByText("Chờ xử lý", {exact: true})).toBeVisible();
  await request.post(`${backend}/control/job-complete`);
  await expect(page.getByRole("link", {name: "Mở hồ sơ ứng viên", exact: true})).toBeVisible();
  await expect(page.getByText("Đã xử lý", {exact: true})).toBeVisible();
  await setupUpload(page); await page.getByLabel("File CV", {exact: true}).setInputFiles(cv());
  await page.getByRole("button", {name: "Upload 1 CV", exact: true}).click();
  await expect(page.getByText("CV đã được xử lý trước đó.", {exact: false})).toBeVisible();
  await page.goto("/ingestion/jobs"); await expect(page.getByRole("heading", {name: "1 tác vụ", exact: true})).toBeVisible();
  await page.screenshot({path: "test-results/ingestion-jobs-desktop.png"});
});

test("queue failure is recoverable and a busy job rejects retry without inventing success", async ({page, request}) => {
  await login(page); await setupUpload(page); await request.post(`${backend}/control/mode`, {data: {mode: "queue-down"}});
  await page.getByLabel("File CV", {exact: true}).setInputFiles(cv()); await page.getByRole("button", {name: "Upload 1 CV", exact: true}).click();
  await page.getByRole("link", {name: "Xem tác vụ", exact: true}).click();
  await expect(page.locator("#ingestion-main [role=alert]")).toContainText("Kiểm tra Redis");
  await page.getByRole("button", {name: "Đưa lại vào hàng đợi", exact: true}).click();
  await page.getByRole("dialog", {name: "Xác nhận xử lý lại CV?", exact: true}).getByRole("button", {name: "Hủy", exact: true}).click();
  let calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.some((c: {path: string}) => c.path.endsWith("/retry"))).toBe(false);
  await request.post(`${backend}/control/mode`, {data: {mode: "job-busy"}});
  await page.getByRole("button", {name: "Đưa lại vào hàng đợi", exact: true}).click();
  await page.getByRole("dialog", {name: "Xác nhận xử lý lại CV?", exact: true}).getByRole("button", {name: "Xác nhận", exact: true}).click();
  await expect(page.locator("#ingestion-main [role=alert]").filter({hasText: "JOB_RUNNING"})).toBeVisible();
  await request.post(`${backend}/control/mode`, {data: {mode: "normal"}});
  await page.getByRole("button", {name: "Đưa lại vào hàng đợi", exact: true}).click();
  await page.getByRole("dialog", {name: "Xác nhận xử lý lại CV?", exact: true}).getByRole("button", {name: "Xác nhận", exact: true}).click();
  await expect(page.getByText("Đã lưu yêu cầu xử lý lại.", {exact: false})).toBeVisible();
  await expect(page.locator("#ingestion-main").getByText("Kiểm tra Redis", {exact: false})).toHaveCount(0);
  calls = await (await request.get(`${backend}/control/calls`)).json(); expect(calls.filter((c: {path: string}) => c.path === "/api/ingestion/uploads")).toHaveLength(1);
});

test("candidate assignment confirms before applying the new department", async ({page, request}) => {
  await login(page); await page.goto("/admin/postings");
  await page.getByLabel("Tên vị trí tuyển dụng", {exact: true}).fill("Account Manager");
  await page.getByLabel("Phòng ban của vị trí", {exact: true}).selectOption(sales);
  await page.getByRole("button", {name: "Tạo mới", exact: true}).click();
  await expect(page.getByText("Account Manager", {exact: true})).toBeVisible();
  await page.goto("/candidates/33333333-3333-4333-8333-000000000001");
  await page.getByLabel("Gán vị trí tuyển dụng", {exact: true}).selectOption({label: "Sales · Account Manager"});
  await page.getByRole("button", {name: "Lưu vị trí", exact: true}).click();
  await page.getByRole("dialog", {name: "Thay đổi vị trí tuyển dụng?", exact: true}).getByRole("button", {name: "Hủy", exact: true}).click();
  let calls = await (await request.get(`${backend}/control/calls`)).json(); expect(calls.some((c: {path: string}) => c.path.endsWith("/posting"))).toBe(false);
  await page.getByRole("button", {name: "Lưu vị trí", exact: true}).click();
  await page.getByRole("dialog", {name: "Thay đổi vị trí tuyển dụng?", exact: true}).getByRole("button", {name: "Xác nhận", exact: true}).click();
  await expect(page.locator(".profile-sidebar").getByRole("link", {name: "Sales", exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: "Lưu vị trí", exact: true})).toBeDisabled();
  calls = await (await request.get(`${backend}/control/calls`)).json(); expect(calls.filter((c: {path: string}) => c.path.endsWith("/posting"))).toHaveLength(1);
});

test("tester cannot open administration or upload and multipart requires same origin", async ({page, request}) => {
  await login(page, "tester_a");
  for (const path of ["/admin/users", "/admin/departments", "/ingestion/upload", "/ingestion/jobs"]) {
    await page.goto(path); await expect(page.getByRole("heading", {name: "Bạn chưa có quyền truy cập", exact: true})).toBeVisible();
  }
  const rejected = await page.request.post(`${origin}/api/backend/ingestion/uploads`, {headers: {Origin: "https://evil.example.test"}, multipart: {posting_id: posting, file: cv()}});
  expect(rejected.status()).toBe(403);
  const forbidden = await page.request.post(`${origin}/api/backend/ingestion/uploads`, {headers: {Origin: origin}, multipart: {posting_id: posting, file: cv()}});
  expect(forbidden.status()).toBe(403);
  const calls = await (await request.get(`${backend}/control/calls`)).json(); expect(calls.some((c: {path: string}) => c.path === "/api/ingestion/uploads")).toBe(false);
});

test("mobile upload validates local file size and has no page overflow", async ({page, request}) => {
  await page.setViewportSize({width: 390, height: 844}); await login(page); await setupUpload(page);
  await page.getByLabel("File CV", {exact: true}).setInputFiles({name: "Small_CV.pdf", mimeType: "application/pdf", buffer: Buffer.from("small")});
  await expect(page.locator("#ingestion-main").getByRole("alert")).toContainText("File nhỏ hơn dung lượng tối thiểu.");
  await expect(page.getByRole("button", {name: "Upload 0 CV", exact: true})).toBeDisabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: "test-results/ingestion-upload-mobile.png"});
  await page.getByRole("button", {name: "Mở điều hướng", exact: true}).click();
  await expect(page.getByRole("dialog", {name: "Điều hướng", exact: true}).getByRole("link", {name: "Quản lý tài khoản", exact: true})).toBeVisible();
  const calls = await (await request.get(`${backend}/control/calls`)).json(); expect(calls.some((c: {path: string}) => c.path === "/api/ingestion/uploads")).toBe(false);
});
