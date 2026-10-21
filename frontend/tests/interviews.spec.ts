import { expect, test, type Page } from "@playwright/test";
const backend = "http://127.0.0.1:28101";
const origin = "http://127.0.0.1:28100";
const candidate = "33333333-3333-4333-8333-000000000001";
async function login(page: Page, username = "sang") {
  await page.goto("/login");
  await page.getByLabel("Tên đăng nhập", {exact: true}).fill(username);
  await page.getByLabel("Mật khẩu", {exact: true}).fill("test-password-123");
  await page.getByRole("button", {name: "Đăng nhập", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Bắt đầu từ một câu hỏi"})).toBeVisible();
}
async function open(page: Page) {
  await login(page); await page.goto(`/interviews?candidate=${candidate}`);
  await expect(page.getByRole("heading", {name: "Chưa có bộ câu hỏi", exact: true})).toBeVisible();
}
async function generate(page: Page) {
  await page.getByLabel("Số câu hỏi", {exact: true}).fill("3");
  await page.getByRole("button", {name: "Sinh bộ câu hỏi", exact: true}).click();
  await expect(page.locator(".interview-question")).toHaveCount(3);
}
test.beforeEach(async ({request}) => {await request.post(`${backend}/control/reset`);});

test("profile links to interviews; generation, grouping, copying and reload persist", async ({page, context, request}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.setViewportSize({width: 1440, height: 1000});
  await login(page); await page.goto(`/candidates/${candidate}?q=Ada&page_size=10`);
  await page.getByRole("link", {name: "Tạo câu hỏi phỏng vấn", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Chưa có bộ câu hỏi", exact: true})).toBeVisible();
  await expect(page.getByRole("link", {name: "Xem hồ sơ ứng viên", exact: true})).toHaveAttribute("href", `/candidates/${candidate}?q=Ada&page_size=10`);
  await generate(page);
  await page.screenshot({path: "test-results/interviews-desktop.png"});
  await page.getByRole("button", {name: "Kỹ thuật (1)", exact: true}).click();
  await expect(page.locator(".interview-question")).toHaveCount(1);
  await expect(page.locator(".interview-evidence")).toContainText("CV mẫu");
  await page.getByRole("button", {name: "Sao chép câu 1", exact: true}).click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain("Căn cứ CV (Dự án): CV mẫu");
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  const mutation = calls.find((c: {method: string; path: string}) => c.method === "POST" && c.path.endsWith("/interview-questions/generate"));
  expect(mutation.body).toEqual({max_questions: 3, expected_revision: "0".repeat(64), replace_existing: false});
  await page.reload(); await expect(page.locator(".interview-question")).toHaveCount(3);
});

test("replace and delete require confirmation and send current revisions", async ({page, request}) => {
  await open(page); await generate(page);
  await page.getByRole("button", {name: "Sinh lại bộ câu hỏi", exact: true}).click();
  const dialog = page.getByRole("dialog", {name: "Thay bộ câu hỏi đã lưu?", exact: true});
  await expect(dialog).toBeVisible(); await dialog.getByRole("button", {name: "Hủy", exact: true}).click();
  const callCount = async () => (await (await request.get(`${backend}/control/calls`)).json()).filter((c: {method: string; path: string}) => c.method === "POST" && c.path.endsWith("/interview-questions/generate")).length;
  expect(await callCount()).toBe(1);
  await page.getByRole("button", {name: "Sinh lại bộ câu hỏi", exact: true}).click();
  await dialog.getByRole("button", {name: "Xác nhận sinh lại", exact: true}).click();
  await expect.poll(callCount).toBe(2);
  await expect(page.getByRole("button", {name: "Sinh lại bộ câu hỏi", exact: true})).toBeEnabled();
  await page.getByRole("button", {name: "Xóa toàn bộ", exact: true}).click();
  const deletion = page.getByRole("dialog", {name: "Xóa toàn bộ câu hỏi?", exact: true});
  await expect(deletion).toBeVisible(); await deletion.getByRole("button", {name: "Xác nhận xóa", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Chưa có bộ câu hỏi", exact: true})).toBeVisible();
  await page.reload(); await expect(page.locator(".interview-question")).toHaveCount(0);
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.find((c: {method: string; path: string}) => c.method === "DELETE" && c.path.endsWith("/interview-questions")).query).toContain("expected_revision=");
});

test("provider failure and stale revision preserve saved questions", async ({page, request}) => {
  await open(page); await generate(page);
  for (const mode of ["interview-fail", "interview-stale"]) {
    await request.post(`${backend}/control/mode`, {data: {mode}});
    await page.getByRole("button", {name: "Sinh lại bộ câu hỏi", exact: true}).click();
    await page.getByRole("dialog").getByRole("button", {name: "Xác nhận sinh lại", exact: true}).click();
    await expect(page.locator("#interview-main [role=alert]")).toBeVisible();
    await expect(page.locator(".interview-question")).toHaveCount(3);
    await expect(page.getByRole("button", {name: "Sinh lại bộ câu hỏi", exact: true})).toBeEnabled();
  }
});

test("timeout recovers saved state by GET and does not repeat generation", async ({page, request}) => {
  await open(page);
  await request.post(`${backend}/control/mode`, {data: {mode: "interview-uncertain"}});
  await generate(page);
  await expect(page.locator("#interview-main [role=alert]")).toContainText("DEPENDENCY_TIMEOUT");
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  const index = calls.findIndex((c: {method: string; path: string}) => c.method === "POST" && c.path.endsWith("/interview-questions/generate"));
  expect(calls.slice(index).filter((c: {method: string}) => c.method === "POST")).toHaveLength(1);
  expect(calls.slice(index).some((c: {method: string; path: string}) => c.method === "GET" && c.path.endsWith("/interview-questions"))).toBe(true);
});

test("candidate picker, validation, no CV and in-progress state", async ({page, request}) => {
  await login(page); await page.goto("/interviews");
  await page.getByLabel("Tên hoặc email ứng viên").fill("Ada");
  await page.getByRole("button", {name: "Tìm", exact: true}).click();
  await page.getByRole("button", {name: /Ada Nguyen/}).click();
  await expect(page.getByRole("heading", {name: "Chưa có bộ câu hỏi", exact: true})).toBeVisible();
  await page.getByLabel("Số câu hỏi", {exact: true}).fill("2");
  await expect(page.getByRole("button", {name: "Sinh bộ câu hỏi", exact: true})).toBeDisabled();
  await expect(page.locator("#interview-main [role=alert]")).toContainText("3 đến 15");
  await request.post(`${backend}/control/mode`, {data: {mode: "interview-busy"}});
  await page.reload();
  await expect(page.getByRole("button", {name: "Đang xử lý…", exact: true})).toBeDisabled();
  await expect(page.getByRole("button", {name: "Đổi ứng viên", exact: true})).toBeDisabled();
  await request.post(`${backend}/control/mode`, {data: {mode: "normal"}});
  await expect(page.getByRole("button", {name: "Sinh bộ câu hỏi", exact: true})).toBeEnabled();
  await page.goto("/interviews?candidate=33333333-3333-4333-8333-000000000023");
  await expect(page.getByText("Ứng viên chưa có nội dung CV để sinh câu hỏi.", {exact: true})).toBeVisible();
  await expect(page.getByRole("button", {name: "Sinh bộ câu hỏi", exact: true})).toBeDisabled();
});

test("interview permissions and BFF method/origin guard", async ({page}) => {
  await page.goto("/interviews"); await expect(page).toHaveURL(/\/login$/);
  await login(page, "tester_a");
  await expect(page.getByRole("link", {name: "Câu hỏi phỏng vấn", exact: true})).toHaveCount(0);
  await page.goto(`/interviews?candidate=${candidate}`);
  await expect(page.getByRole("heading", {name: "Bạn chưa có quyền truy cập", exact: true})).toBeVisible();
  const path = `/api/backend/candidates/${candidate}/interview-questions`;
  expect((await page.request.get(path)).status()).toBe(403);
  expect((await page.request.post(path + "/generate", {headers: {origin}, data: {max_questions: 8, expected_revision: "0".repeat(64)}})).status()).toBe(403);
  expect((await page.request.delete(path + "?expected_revision=" + "0".repeat(64), {headers: {origin}})).status()).toBe(403);
  expect((await page.request.post(path + "/generate", {headers: {origin: "https://evil.example"}, data: {}})).status()).toBe(403);
  expect((await page.request.post(path, {headers: {origin}, data: {}})).status()).toBe(404);
});

test("mobile interview layout and navigation", async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await open(page); await generate(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({path: "test-results/interviews-mobile.png"});
  await page.getByRole("button", {name: "Mở điều hướng", exact: true}).click();
  await expect(page.getByRole("dialog", {name: "Điều hướng", exact: true})).toBeVisible();
  await page.getByRole("dialog").getByRole("link", {name: "Ứng viên", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Ứng viên", exact: true})).toBeVisible();
});
