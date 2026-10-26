import { expect, test, type Page } from "@playwright/test";
const backend = "http://127.0.0.1:28101";
async function login(page: Page, username = "sang") {
  await page.goto("/login"); await page.getByLabel("Tên đăng nhập", {exact: true}).fill(username);
  await page.getByLabel("Mật khẩu", {exact: true}).fill("test-password-123");
  await page.getByRole("button", {name: "Đăng nhập", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Bắt đầu từ một câu hỏi"})).toBeVisible();
}
test.beforeEach(async ({request}) => {await request.post(`${backend}/control/reset`);});
test("ops free cost, details, pagination, filters and alert link", async ({page, request}) => {
  await page.setViewportSize({width: 1440, height: 1000}); await login(page);
  await page.getByRole("link", {name: "System Ops", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Giám sát vận hành AI"})).toBeVisible();
  await expect(page.locator(".ops-kpis")).toContainText("$0.000000");
  await page.getByRole("button", {name: "Chi tiết call 1", exact: true}).click();
  await expect(page.getByRole("dialog")).toContainText("operation-fixture");
  await expect(page.getByRole("dialog")).toContainText("không phải số lượt trúng cache Redis");
  await page.keyboard.press("Escape");
  await page.getByRole("button", {name: "Trang sau", exact: true}).click();
  await expect(page.getByRole("button", {name: "Chi tiết call 26", exact: true})).toBeVisible();
  await page.getByLabel("Model", {exact: true}).selectOption("unknown");
  await page.getByRole("button", {name: "Áp dụng", exact: true}).click();
  await expect(page.locator(".ops-kpis")).toContainText("Chưa xác định");
  await expect(page.locator(".ops-kpis")).toContainText("27 lần gọi chưa xác định chi phí");
  await page.getByRole("button", {name: "Xem các call cảnh báo"}).click();
  await expect(page.getByRole("heading", {name: "Lịch sử gọi AI (1)", exact: true})).toBeVisible();
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.some((c: {path: string; query: string}) => c.path === "/api/ops/dashboard" && c.query.includes("model=unknown") && c.query.includes("alerts_only=true"))).toBeTruthy();
  await page.screenshot({path: "test-results/ops-desktop.png", fullPage: true});
  await page.getByRole("link", {name: "Kiểm tra tác vụ lỗi"}).click();
  await expect(page).toHaveURL(/\/ingestion\/jobs\?status=dlq/);
});
test("ops empty, service error recovery and mobile layout", async ({page, request}) => {
  await page.setViewportSize({width: 390, height: 844}); await login(page);
  await request.post(`${backend}/control/mode`, {data: {mode: "ops-empty"}});
  await page.goto("/ops");
  await expect(page.locator("p[role=status]")).toContainText("Chưa có usage khớp bộ lọc");
  await expect(page.getByRole("link", {name: "Kiểm tra tác vụ lỗi"})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({path: "test-results/ops-mobile.png", fullPage: true});
  await request.post(`${backend}/control/mode`, {data: {mode: "ops-down"}});
  await page.getByRole("button", {name: "Làm mới", exact: true}).click();
  await expect(page.locator("#ops-main [role=alert]")).toContainText("DEPENDENCY_UNAVAILABLE");
  await request.post(`${backend}/control/mode`, {data: {mode: "normal"}});
  await page.getByRole("button", {name: "Làm mới", exact: true}).click();
  await expect(page.locator(".ops-kpis")).toContainText("$0.000000");
});
test("tester denied by page and BFF, no mutation allowed", async ({page}) => {
  await login(page, "alice"); await page.goto("/ops");
  await expect(page.getByRole("heading", {name: "Bạn chưa có quyền truy cập"})).toBeVisible();
  expect(await page.evaluate(async () => (await fetch("/api/backend/ops/dashboard")).status)).toBe(403);
  expect(await page.evaluate(async () => (await fetch("/api/backend/ops/dashboard", {method:"POST"})).status)).toBe(404);
});
