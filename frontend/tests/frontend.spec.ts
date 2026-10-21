import { test, expect, type Page } from "@playwright/test";

const origin = "http://127.0.0.1:28100";
const backend = "http://127.0.0.1:28101";
async function login(page: Page, username = "tester_a") {
  await page.goto("/login");
  await page.getByLabel("Tên đăng nhập", {exact: true}).fill(username);
  await page.getByLabel("Mật khẩu", {exact: true}).fill("test-password-123");
  await page.getByRole("button", {name: "Đăng nhập", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Bắt đầu từ một câu hỏi"})).toBeVisible();
}
async function send(page: Page, question = "Ứng viên nào biết Python?") {
  await page.getByLabel("Câu hỏi của bạn").fill(question);
  await page.getByRole("button", {name: "Gửi câu hỏi"}).click();
}
test.beforeEach(async ({request}) => { await request.post(`${backend}/control/reset`); });

test("BFF hides tokens, uses private HttpOnly cookie, enforces origin and allowlist", async ({request}) => {
  const body = {username: "tester_a", password: "test-password-123"};
  expect((await request.post("/api/session/login", {data: body})).status()).toBe(403);
  expect((await request.post("/api/session/login", {headers: {origin: "https://evil.example"}, data: body})).status()).toBe(403);
  const response = await request.post("/api/session/login", {headers: {origin}, data: body});
  expect(response.status()).toBe(200);
  expect(await response.json()).not.toHaveProperty("access_token");
  expect(response.headers()["set-cookie"]).toMatch(/HttpOnly/i);
  expect(response.headers()["set-cookie"]).toMatch(/SameSite=lax/i);
  expect(response.headers()["cache-control"]).toContain("no-store");
  const cookies = (await request.storageState()).cookies;
  expect(cookies[0].expires).toBeLessThanOrEqual(Date.now() / 1000 + 3600);
  expect((await request.get("/api/session/me")).status()).toBe(200);
  expect((await request.get("/api/backend/auth/me")).status()).toBe(404);
  expect((await request.post("/api/backend/conversations", {data: {}})).status()).toBe(403);
  const logout = await request.post("/api/session/logout", {headers: {origin}, data: {}});
  expect(logout.status()).toBe(204);
  expect((await request.get("/api/session/me")).status()).toBe(401);
});

test("login errors, reload, logout and browser storage", async ({page}) => {
  await page.setViewportSize({width: 1440, height: 1000});
  await page.goto("/chat"); await expect(page).toHaveURL(/\/login$/);
  await page.screenshot({path: "test-results/preview-login-desktop.png"});
  await page.getByLabel("Tên đăng nhập", {exact: true}).fill("tester_a");
  await page.getByLabel("Mật khẩu", {exact: true}).fill("wrong");
  await page.getByRole("button", {name: "Hiện mật khẩu"}).click();
  await expect(page.getByLabel("Mật khẩu", {exact: true})).toHaveAttribute("type", "text");
  await page.getByRole("button", {name: "Đăng nhập", exact: true}).click();
  await expect(page.locator(".notice[role=alert]")).toBeVisible();
  await page.getByLabel("Mật khẩu", {exact: true}).fill("test-password-123");
  await page.getByRole("button", {name: "Đăng nhập", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Bắt đầu từ một câu hỏi"})).toBeVisible();
  await page.reload(); await expect(page.getByRole("heading", {name: "Bắt đầu từ một câu hỏi"})).toBeVisible();
  await page.screenshot({path: "test-results/preview-chat-desktop.png"});
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
  expect(await page.evaluate(() => document.cookie)).not.toContain("cv_session");
  await page.getByRole("button", {name: "Đăng xuất", exact: true}).click();
  await expect(page).toHaveURL(/signed-out/);
  await page.goto("/chat"); await expect(page).toHaveURL(/\/login$/);
});

test("logout outage preserves revocable session; revocation redirects on next request", async ({page, request}) => {
  await login(page);
  await request.post(`${backend}/control/mode`, {data: {mode: "logout-down"}});
  await page.getByRole("button", {name: "Đăng xuất", exact: true}).click();
  await expect(page.locator(".notice[role=alert]")).toContainText("DEPENDENCY_UNAVAILABLE");
  expect((await page.context().cookies()).some(c => c.name === "cv_session")).toBe(true);
  await request.post(`${backend}/control/revoke`);
  await page.reload(); await expect(page).toHaveURL(/reason=expired/);
  expect((await page.context().cookies()).some(c => c.name === "cv_session")).toBe(false);
});

test("logout updates other tabs and switching accounts clears the old draft", async ({page, context}) => {
  await login(page, "sang");
  await expect(page.locator(".desktop-sidebar").getByText("Quản trị viên", {exact: true})).toBeVisible();
  const second = await context.newPage();
  await second.goto("/chat");
  await second.getByLabel("Câu hỏi của bạn").fill("Private unsent draft");
  await page.getByRole("button", {name: "Đăng xuất", exact: true}).click();
  await expect(page).toHaveURL(/signed-out/);
  await expect(second).toHaveURL(/\/login/);
  await login(second, "tester_b");
  await expect(second.getByLabel("Câu hỏi của bạn")).toHaveValue("");
  await expect(second.locator(".desktop-sidebar").getByText("tester_b", {exact: true})).toBeVisible();
});

test("admin can list, open, send to and delete a legacy non-UUID conversation", async ({page, request}) => {
  await request.post(`${backend}/control/seed-legacy`);
  await login(page, "sang");
  await page.getByRole("button", {name: /^Hội thoại cũ của admin/}).click();
  await expect(page).toHaveURL(/thread=test-cart/);
  await expect(page.getByText("Hội thoại chưa có tin nhắn.", {exact: false})).toBeVisible();
  await send(page, "Tiếp tục hội thoại cũ");
  await expect(page.getByText("Tìm thấy ứng viên có kỹ năng Python và SQL.")).toBeVisible();
  await page.getByRole("button", {name: "Câu trả lời hữu ích", exact: true}).click();
  await expect(page.getByText("Đã gửi đánh giá")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Tìm thấy ứng viên có kỹ năng Python và SQL.")).toBeVisible();
  await page.getByRole("button", {name: /^Xóa hội thoại/}).click();
  await page.getByRole("dialog").getByRole("button", {name: "Xóa hội thoại", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Bắt đầu từ một câu hỏi"})).toBeVisible();
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.filter((c: {path: string; method: string}) => c.path === "/api/conversations/test-cart/messages" && c.method === "POST")).toHaveLength(1);
  expect(calls.some((c: {path: string; method: string}) => c.path === "/api/conversations/test-cart" && c.method === "DELETE")).toBe(true);
});

test("invalid backend data shows a readable error instead of validator JSON", async ({page, request}) => {
  await request.post(`${backend}/control/mode`, {data: {mode: "bad-list"}});
  await login(page, "sang");
  await expect(page.locator(".desktop-sidebar .notice[role=alert]")).toContainText("Dữ liệu phản hồi từ máy chủ chưa đúng định dạng");
  await expect(page.locator(".desktop-sidebar .notice[role=alert]")).not.toContainText("invalid_format");
  await expect(page.locator(".desktop-sidebar .notice[role=alert]")).not.toContainText("thread_id");
  await expect(page.getByLabel("Câu hỏi của bạn")).toBeVisible();
});

test("real BFF roundtrip: send, feedback once, reload history and delete", async ({page, request}) => {
  await login(page); await send(page);
  await expect(page.getByText("Tìm thấy ứng viên có kỹ năng Python và SQL.")).toBeVisible();
  await page.getByRole("button", {name: "Câu trả lời hữu ích", exact: true}).click();
  await expect(page.getByText("Đã gửi đánh giá")).toBeVisible();
  await expect(page.getByRole("button", {name: "Câu trả lời hữu ích", exact: true})).toBeDisabled();
  await page.reload(); await expect(page.getByText("Tìm thấy ứng viên có kỹ năng Python và SQL.")).toBeVisible();
  await page.getByRole("button", {name: /^Xóa hội thoại/}).click();
  await page.getByRole("button", {name: "Giữ lại", exact: true}).click();
  await expect(page.getByText("Tìm thấy ứng viên có kỹ năng Python và SQL.")).toBeVisible();
  await page.getByRole("button", {name: /^Xóa hội thoại/}).click();
  await page.getByRole("dialog").getByRole("button", {name: "Xóa hội thoại", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Bắt đầu từ một câu hỏi"})).toBeVisible();
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.filter((c: {path: string}) => c.path.endsWith("/feedback"))).toHaveLength(1);
});

test("JD partial edits preserve zero, exact IDs and sibling drafts", async ({page, request}) => {
  await request.post(`${backend}/control/mode`, {data: {mode: "multiple"}});
  await login(page); await send(page, "Tìm ứng viên theo JD");
  const forms = page.locator(".criteria-form");
  await expect(forms).toHaveCount(2);
  await forms.nth(1).getByLabel("Vị trí tuyển dụng").fill("Draft preserved");
  await forms.first().getByLabel("Số năm kinh nghiệm tối thiểu").fill("0");
  await forms.first().getByRole("button", {name: "Xác nhận và tìm ứng viên"}).click();
  await expect(forms).toHaveCount(1);
  await expect(forms.getByLabel("Vị trí tuyển dụng")).toHaveValue("Draft preserved");
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  const resume = calls.find((c: {path: string}) => c.path.endsWith("/resume"));
  expect(resume.body).toEqual({confirmation_id: "confirm-1", confirmed: true, edited_criteria: {min_years_experience: 0}});
  await forms.getByRole("button", {name: "Hủy yêu cầu"}).click();
  await expect(forms).toHaveCount(0); await expect(page.getByLabel("Câu hỏi của bạn")).toBeVisible();
});

test("stale confirmation requires refresh before another resume", async ({page, request}) => {
  await request.post(`${backend}/control/mode`, {data: {mode: "jd"}});
  await login(page); await send(page);
  await expect(page.locator(".criteria-form")).toBeVisible();
  await request.post(`${backend}/control/mode`, {data: {mode: "stale"}});
  await page.getByRole("button", {name: "Xác nhận và tìm ứng viên"}).click();
  await expect(page.getByRole("button", {name: "Xác nhận và tìm ứng viên"})).toBeDisabled();
  await page.getByRole("button", {name: "Kiểm tra trạng thái", exact: true}).click();
  await expect(page.getByRole("button", {name: "Xác nhận và tìm ứng viên"})).toBeEnabled();
  await page.getByRole("button", {name: "Hủy yêu cầu"}).click();
  await expect(page.locator(".criteria-form")).toHaveCount(0);
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.filter((c: {path: string}) => c.path.endsWith("/resume")).map((c: {body: {confirmation_id: string}}) => c.body.confirmation_id)).toEqual(["confirm-1", "confirm-fresh"]);
});

test("timeout recovers by GET without repeating the model request", async ({page, request}) => {
  await request.post(`${backend}/control/mode`, {data: {mode: "uncertain"}});
  await login(page); await send(page);
  await expect(page.locator(".notice[role=alert]")).toContainText("DEPENDENCY_TIMEOUT");
  await expect(page.getByLabel("Câu hỏi của bạn")).toHaveCount(0);
  await page.getByRole("button", {name: "Kiểm tra trạng thái", exact: true}).click();
  await expect(page.getByText("Tìm thấy ứng viên có kỹ năng Python và SQL.")).toBeVisible();
  await expect(page.getByLabel("Câu hỏi của bạn")).toHaveValue("");
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.filter((c: {method: string; path: string}) => c.method === "POST" && c.path.endsWith("/messages"))).toHaveLength(1);
});

test("failed execution stays blocked after recovery and allows a new conversation", async ({page, request}) => {
  await request.post(`${backend}/control/mode`, {data: {mode: "incomplete"}});
  await login(page); await send(page);
  await page.getByRole("button", {name: "Kiểm tra trạng thái", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Lượt xử lý chưa hoàn tất"})).toBeVisible();
  await expect(page.getByLabel("Câu hỏi của bạn")).toHaveCount(0);
  await page.getByRole("button", {name: "Mở cuộc trò chuyện mới", exact: true}).click();
  await expect(page.getByLabel("Câu hỏi của bạn")).toBeVisible();
});

test("JD rejects invalid Top-K and maps empty years to null", async ({page, request}) => {
  await request.post(`${backend}/control/mode`, {data: {mode: "jd"}});
  await login(page); await send(page);
  await page.getByLabel("Số ứng viên (Top-K)").fill("11");
  await page.getByRole("button", {name: "Xác nhận và tìm ứng viên"}).click();
  await expect(page.locator(".criteria-form")).toBeVisible();
  let calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.filter((c: {path: string}) => c.path.endsWith("/resume"))).toHaveLength(0);
  await page.getByLabel("Số ứng viên (Top-K)").fill("3");
  await page.getByLabel("Số năm kinh nghiệm tối thiểu").fill("");
  await page.getByRole("button", {name: "Xác nhận và tìm ứng viên"}).click();
  await expect(page.locator(".criteria-form")).toHaveCount(0);
  calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.find((c: {path: string}) => c.path.endsWith("/resume")).body.edited_criteria).toEqual({min_years_experience: null});
});

test("cleanup retries the tombstoned ID", async ({page, request}) => {
  await login(page); await send(page);
  await expect(page.getByText("Tìm thấy ứng viên có kỹ năng Python và SQL.")).toBeVisible();
  await request.post(`${backend}/control/mode`, {data: {mode: "cleanup"}});
  await page.getByRole("button", {name: /^Xóa hội thoại/}).click();
  await page.getByRole("dialog").getByRole("button", {name: "Xóa hội thoại", exact: true}).click();
  await expect(page.getByRole("button", {name: "Hoàn tất xóa"})).toBeVisible();
  await page.getByRole("button", {name: "Hoàn tất xóa"}).click();
  await expect(page.getByRole("button", {name: "Hoàn tất xóa"})).toHaveCount(0);
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  const deletions = calls.filter((c: {method: string}) => c.method === "DELETE");
  expect(deletions).toHaveLength(2); expect(deletions[0].path).toBe(deletions[1].path);
});

test("two accounts have separate conversation lists and ownership", async ({browser, request}) => {
  const a = await browser.newContext(), b = await browser.newContext();
  const pa = await a.newPage(), pb = await b.newPage();
  await login(pa, "tester_a"); await send(pa, "Private A");
  await expect(pa.getByText("Tìm thấy ứng viên có kỹ năng Python và SQL.")).toBeVisible();
  const thread = new URL(pa.url()).searchParams.get("thread");
  await login(pb, "tester_b"); await expect(pb.getByRole("button", {name: /Private A/})).toHaveCount(0);
  expect((await b.request.get(`${origin}/api/backend/conversations/${thread}/messages`)).status()).toBe(404);
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.some((c: {path: string}) => c.path === `/api/conversations/${thread}/messages`)).toBe(true);
  await a.close(); await b.close();
});

test("mobile layout, accessible drawer and JD actions", async ({page, request}) => {
  await page.setViewportSize({width: 320, height: 740});
  await request.post(`${backend}/control/mode`, {data: {mode: "jd"}});
  await login(page);
  await page.getByRole("button", {name: "Mở danh sách hội thoại"}).click();
  await expect(page.getByRole("dialog", {name: "Hội thoại của bạn"})).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", {name: "Mở danh sách hội thoại"})).toBeFocused();
  await send(page); await expect(page.locator(".criteria-form")).toBeVisible();
  await page.getByRole("button", {name: "Xác nhận và tìm ứng viên"}).scrollIntoViewIfNeeded();
  await page.screenshot({path: "test-results/preview-jd-mobile.png"});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole("button", {name: "Hủy yêu cầu"}).click();
  await expect(page.getByLabel("Câu hỏi của bạn")).toBeVisible();
});
