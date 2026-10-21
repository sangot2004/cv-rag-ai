import { expect, test, type Page } from "@playwright/test";
const backend = "http://127.0.0.1:28101", origin = "http://127.0.0.1:28100";
const candidate = "33333333-3333-4333-8333-000000000001";
async function login(page: Page, username = "sang") {
  await page.goto("/login"); await page.getByLabel("Tên đăng nhập", {exact: true}).fill(username);
  await page.getByLabel("Mật khẩu", {exact: true}).fill("test-password-123");
  await page.getByRole("button", {name: "Đăng nhập", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Bắt đầu từ một câu hỏi"})).toBeVisible();
}
async function setup(page: Page, bulk = false) {
  await page.goto(bulk ? "/emails/bulk" : `/emails/compose?candidate=${candidate}`);
  if (bulk) {await page.getByLabel("Chọn Ada Nguyen", {exact: true}).check(); await page.getByLabel("Chọn Ứng viên 02", {exact: true}).check();}
  else await expect(page.getByLabel("Chọn Ada Nguyen", {exact: true})).toBeChecked();
  await page.getByLabel("Tên đợt gửi / bản nháp", {exact: true}).fill(bulk ? "Đợt phỏng vấn tháng 12" : "Mời Ada phỏng vấn");
  await page.getByLabel("Ngày phỏng vấn", {exact: true}).fill("2026-12-01");
  await page.getByLabel("Giờ phỏng vấn (Việt Nam)", {exact: true}).fill("10:00");
  await page.getByLabel("Link phỏng vấn", {exact: true}).fill("https://meet.example.test/interview");
  await page.getByRole("button", {name: "Tạo bản nháp", exact: true}).click();
  await expect(page).toHaveURL(/\/emails\/batches\/[a-f0-9-]+$/);
  await expect(page.getByRole("button", {name: "Tạo nháp AI còn thiếu", exact: true})).toBeEnabled();
}
async function generate(page: Page) {
  await page.getByRole("button", {name: "Tạo nháp AI còn thiếu", exact: true}).click();
  await expect(page.getByText(/Đã tạo \d+ nháp/)).toBeVisible();
  await expect(page.getByRole("button", {name: "Tạo nháp AI còn thiếu", exact: true})).toBeDisabled();
}
async function approve(page: Page, bulk = false) {
  if (bulk) await page.getByRole("button", {name: "Chọn tất cả nháp hợp lệ đã lưu", exact: true}).click();
  await page.getByRole("button", {name: bulk ? "Duyệt & gửi 2 thư" : "Xem lại & xác nhận gửi", exact: true}).click();
  const dialog = page.getByRole("dialog", {name: bulk ? "Xác nhận gửi 2 thư mời?" : "Xác nhận gửi 1 thư mời?", exact: true});
  await expect(dialog).toBeVisible(); await expect(dialog).toContainText("ada@example.test");
  await dialog.getByRole("button", {name: "Xác nhận", exact: true}).click();
  await expect(page.getByRole("heading", {name: /Kết quả từng người nhận/})).toBeVisible();
}
test.beforeEach(async ({request}) => {await request.post(`${backend}/control/reset`);});

test("single invitation drafts persist, preview is safe, explicit approval and history", async ({page, request}) => {
  await page.setViewportSize({width: 1440, height: 1000}); await login(page);
  await setup(page); await generate(page);
  const card = page.getByRole("article", {name: "Nháp Ada Nguyen", exact: true});
  await card.getByLabel("Tiêu đề thư", {exact: true}).fill("Thư được HR duyệt");
  await card.getByLabel("Nội dung thư", {exact: true}).fill("Xin chào Ada. <script>unsafe()</script>\nHẹn gặp lúc 10:00.");
  await expect(page.getByRole("button", {name: "Xem lại & xác nhận gửi", exact: true})).toBeDisabled();
  await card.getByRole("button", {name: "Lưu bản nháp", exact: true}).click();
  await expect(page.getByText("Đã lưu bản nháp.", {exact: true})).toBeVisible();
  await page.reload();
  const stored = page.getByRole("article", {name: "Nháp Ada Nguyen", exact: true});
  await expect(stored.getByLabel("Tiêu đề thư", {exact: true})).toHaveValue("Thư được HR duyệt");
  await stored.getByRole("button", {name: "Xem trước", exact: true}).click();
  await expect(stored.locator(".email-preview")).toContainText("<script>unsafe()</script>");
  let calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.some((c: {path: string}) => c.path.endsWith("/dispatch"))).toBe(false);
  await page.screenshot({path: "test-results/email-compose-desktop.png"});
  await approve(page);
  await page.screenshot({path: "test-results/email-progress-desktop.png"});
  await request.post(`${backend}/control/email-complete`, {data: {status: "success"}});
  await expect(page.locator(".email-delivery .badge")).toHaveText("Đã gửi");
  await page.getByRole("link", {name: "Lịch sử gửi thư", exact: true}).last().click();
  await expect(page.getByRole("heading", {name: "1 thư", exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Xem thư gửi Ada Nguyen", exact: true}).click();
  await expect(page.getByRole("dialog", {name: "Nội dung thư đã lưu", exact: true})).toContainText("Thư được HR duyệt");
  await page.screenshot({path: "test-results/email-history-desktop.png"});
  calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.filter((c: {path: string}) => c.path.endsWith("/dispatch"))).toHaveLength(1);
});

test("bulk drafts can be reviewed separately; cancel approval sends nothing", async ({page, request}) => {
  await login(page); await setup(page, true); await generate(page);
  await page.getByLabel("Duyệt Ada Nguyen", {exact: true}).check();
  await page.getByRole("button", {name: "Duyệt & gửi 1 thư", exact: true}).click();
  const dialog = page.getByRole("dialog", {name: "Xác nhận gửi 1 thư mời?", exact: true});
  await expect(dialog).not.toContainText("binh@example.test");
  await dialog.getByRole("button", {name: "Hủy", exact: true}).click();
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.some((c: {path: string}) => c.path.endsWith("/dispatch"))).toBe(false);
  await approve(page, true);
  await page.screenshot({path: "test-results/email-bulk-progress.png"});
  await request.post(`${backend}/control/email-complete`, {data: {status: "failed"}});
  await expect(page.getByRole("button", {name: "Thử gửi lại", exact: true})).toHaveCount(2);
  await page.getByRole("button", {name: "Thử gửi lại", exact: true}).first().click();
  await page.getByRole("dialog", {name: "Xác nhận thử gửi lại?", exact: true}).getByRole("button", {name: "Xác nhận", exact: true}).click();
  await expect.poll(async () => (await (await request.get(`${backend}/control/calls`)).json()).filter((c: {path: string}) => c.path.endsWith("/retry")).length).toBe(1);
});

test("AI failure preserves a saved draft; stale writes have clear errors", async ({page, request}) => {
  await login(page); await setup(page); await generate(page);
  await request.post(`${backend}/control/mode`, {data: {mode: "email-ai-fail"}});
  await page.getByRole("button", {name: "Tạo nháp AI", exact: true}).click();
  await page.getByRole("dialog", {name: "Tạo lại nội dung nháp?", exact: true}).getByRole("button", {name: "Xác nhận", exact: true}).click();
  await expect(page.locator("#email-main [role=alert]")).toContainText("DEPENDENCY_UNAVAILABLE");
  await expect(page.getByLabel("Tiêu đề thư", {exact: true})).toHaveValue("Thư mời Ada Nguyen");
  await request.post(`${backend}/control/mode`, {data: {mode: "email-stale"}});
  await page.getByLabel("Tiêu đề thư", {exact: true}).fill("Changed");
  await page.getByRole("button", {name: "Lưu bản nháp", exact: true}).click();
  await expect(page.locator("#email-main [role=alert]")).toContainText("STALE_EMAIL_DRAFT");
  await expect(page.getByLabel("Tiêu đề thư", {exact: true})).toHaveValue("Thư mời Ada Nguyen");
});

test("dispatch timeout recovers frozen queued state without resending; unknown only reconciles", async ({page, request}) => {
  await login(page); await setup(page); await generate(page);
  await request.post(`${backend}/control/mode`, {data: {mode: "email-dispatch-timeout"}});
  await approve(page);
  await expect(page.locator("#email-main [role=alert]")).toContainText("DEPENDENCY_TIMEOUT");
  await request.post(`${backend}/control/email-complete`, {data: {status: "unknown"}});
  await expect(page.getByRole("button", {name: "Kiểm tra Gmail", exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: "Thử gửi lại", exact: true})).toHaveCount(0);
  await page.getByRole("button", {name: "Kiểm tra Gmail", exact: true}).click();
  await expect(page.locator(".email-delivery .badge")).toHaveText("Đã gửi");
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.filter((c: {path: string}) => c.path.endsWith("/dispatch"))).toHaveLength(1);
});

test("previously invited recipients require another explicit acknowledgement", async ({page, request}) => {
  await login(page); await setup(page); await generate(page); await approve(page);
  await request.post(`${backend}/control/email-complete`, {data: {status: "success"}});
  await setup(page); await generate(page);
  await expect(page.getByText("Địa chỉ/ứng viên này đã từng được gửi thư mời.", {exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: "Xem lại & xác nhận gửi", exact: true})).toBeDisabled();
  await page.getByLabel("Tôi xác nhận gửi thêm cho những người đã từng nhận thư mời.", {exact: true}).check();
  await expect(page.getByRole("button", {name: "Xem lại & xác nhận gửi", exact: true})).toBeEnabled();
});

test("history filters and persistent batch listing", async ({page, request}) => {
  await login(page); await setup(page); await generate(page); await approve(page);
  await request.post(`${backend}/control/email-complete`, {data: {status: "success"}});
  await page.goto("/emails/history");
  await page.getByLabel("Tìm thư", {exact: true}).fill("Nobody");
  await page.getByRole("button", {name: "Lọc lịch sử", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Chưa có thư trong lịch sử", exact: true})).toBeVisible();
  await page.reload(); await expect(page.getByLabel("Tìm thư", {exact: true})).toHaveValue("Nobody");
  await page.goto("/emails/batches");
  await page.getByRole("link", {name: /Mời Ada phỏng vấn/}).click();
  await expect(page.getByRole("heading", {name: /Kết quả từng người nhận/})).toBeVisible();
});

test("mail permissions, BFF origin guard and mobile layout", async ({page}) => {
  await page.goto("/emails/compose"); await expect(page).toHaveURL(/\/login$/);
  await login(page, "tester_a");
  for (const path of ["/emails/compose", "/emails/bulk", "/emails/history", "/emails/batches"]) {await page.goto(path); await expect(page.getByRole("heading", {name: "Bạn chưa có quyền truy cập", exact: true})).toBeVisible();}
  expect((await page.request.get("/api/backend/emails/history")).status()).toBe(403);
  expect((await page.request.post("/api/backend/emails/batches", {headers: {origin: "https://evil.example"}, data: {}})).status()).toBe(403);
  expect((await page.request.post("/api/backend/emails/history", {headers: {origin}, data: {}})).status()).toBe(404);
  await page.context().clearCookies();
  await page.setViewportSize({width: 390, height: 844}); await login(page); await setup(page); await generate(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({path: "test-results/email-compose-mobile.png"});
});
