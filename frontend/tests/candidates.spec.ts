import { test, expect, type Page } from "@playwright/test";
const backend = "http://127.0.0.1:28101";
const origin = "http://127.0.0.1:28100";
const ada = "33333333-3333-4333-8333-000000000001";
async function login(page: Page, username = "sang") {
  await page.goto("/login");
  await page.getByLabel("Tên đăng nhập", {exact: true}).fill(username);
  await page.getByLabel("Mật khẩu", {exact: true}).fill("test-password-123");
  await page.getByRole("button", {name: "Đăng nhập", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Bắt đầu từ một câu hỏi"})).toBeVisible();
}
test.beforeEach(async ({request}) => {await request.post(`${backend}/control/reset`);});

test("admin filters, reads full profile and returns with URL filters preserved", async ({page, request}) => {
  await page.setViewportSize({width: 1440, height: 1000});
  await login(page);
  await page.getByRole("link", {name: "Ứng viên", exact: true}).first().click();
  await expect(page.getByRole("heading", {name: "23 ứng viên"})).toBeVisible();
  await page.screenshot({path: "test-results/candidates-desktop.png", fullPage: true});
  await page.getByLabel("Tìm tên hoặc email").fill("Ada");
  await page.getByLabel("Kỹ năng", {exact: true}).fill("Python, SQL");
  await page.getByText("Bộ lọc nâng cao", {exact:false}).click();
  await page.getByLabel("Kinh nghiệm tối thiểu (năm)").fill("0");
  await page.getByRole("button", {name: "Áp dụng bộ lọc"}).click();
  await expect(page.getByRole("heading", {name: "1 ứng viên", exact: true})).toBeVisible();
  const listURL = page.url();
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  const query = new URLSearchParams(calls.filter((c: {path: string}) => c.path === "/api/candidates").at(-1).query);
  expect(query.getAll("skills")).toEqual(["Python", "SQL"]);
  expect(query.get("min_years_experience")).toBe("0");
  await page.getByRole("link", {name: /Ada Nguyen/}).click();
  await expect(page.getByRole("heading", {name: "Ada Nguyen", exact: true})).toBeVisible();
  await expect(page.getByText("Kinh nghiệm: 0 năm", {exact: true})).toBeVisible();
  for (const heading of ["Kinh nghiệm làm việc", "Học vấn", "Chứng chỉ", "Dự án"]) await expect(page.getByRole("heading", {name: heading, exact: true})).toBeVisible();
  await page.getByText("Nội dung CV đã trích xuất", {exact: true}).click();
  await expect(page.locator(".raw-cv")).toContainText("<script>alert('unsafe')</script>");
  await page.screenshot({path: "test-results/candidate-profile-desktop.png", fullPage: true});
  await page.getByRole("link", {name: "Quay lại danh sách"}).click();
  await expect(page).toHaveURL(listURL);
  await expect(page.getByLabel("Kỹ năng", {exact: true})).toHaveValue("Python, SQL");
  await page.reload();
  await expect(page.getByLabel("Tìm tên hoặc email")).toHaveValue("Ada");
});

test("pagination, group filters and browser back keep list state", async ({page, request}) => {
  await login(page); await page.goto("/candidates?page_size=10");
  await expect(page.getByText("Trang 1 / 3", {exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Trang sau", exact: true}).click();
  await expect(page.getByText("Trang 2 / 3", {exact: true})).toBeVisible();
  await page.getByRole("link", {name: /Ứng viên 11/}).click();
  await expect(page.getByRole("heading", {name: "Ứng viên 11", exact: true})).toBeVisible();
  await page.goBack();
  await expect(page.getByText("Trang 2 / 3", {exact: true})).toBeVisible();
  await page.getByRole("link", {name: "Engineering", exact: true}).first().click();
  await expect(page.getByRole("heading", {name: "22 ứng viên"})).toBeVisible();
  await expect(page.getByText("Trang 1 / 3", {exact: true})).toBeVisible();
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.filter((c: {path: string}) => c.path === "/api/candidates").at(-1).query).not.toContain("department_name");
  await page.getByRole("button", {name: /Phòng ban: Engineering/}).click();
  await expect(page.getByRole("heading", {name: "23 ứng viên"})).toBeVisible();
});

test("empty, validation, unavailable, malformed and missing profiles have recovery", async ({page, request}) => {
  await login(page); await page.goto("/candidates");
  await page.getByText("Bộ lọc nâng cao", {exact:false}).click();
  await page.getByLabel("Kinh nghiệm tối thiểu (năm)").fill("5");
  await page.getByLabel("Kinh nghiệm tối đa (năm)").fill("0");
  await page.getByRole("button", {name: "Áp dụng bộ lọc"}).click();
  await expect(page.locator("#candidate-main [role=alert]")).toContainText("tối thiểu");
  await page.goto("/candidates?q=Nobody");
  await expect(page.getByRole("heading", {name: "Không tìm thấy ứng viên"})).toBeVisible();
  await page.goto("/candidates/44444444-4444-4444-8444-444444444444");
  await expect(page.getByRole("heading", {name: "Không tìm thấy ứng viên"})).toBeVisible();
  await request.post(`${backend}/control/mode`, {data: {mode: "candidate-down"}});
  await page.goto("/candidates"); await expect(page.locator("#candidate-main [role=alert]")).toContainText("DEPENDENCY_UNAVAILABLE");
  await request.post(`${backend}/control/mode`, {data: {mode: "normal"}});
  await page.getByRole("button", {name: "Thử lại", exact: true}).click();
  await expect(page.getByRole("heading", {name: "23 ứng viên"})).toBeVisible();
  await request.post(`${backend}/control/mode`, {data: {mode: "candidate-bad"}});
  await page.reload(); await expect(page.locator("#candidate-main [role=alert]")).toContainText("Dữ liệu phản hồi");
});

test("tester can browse own department, but has no admin actions", async ({page}) => {
  await page.goto("/candidates"); await expect(page).toHaveURL(/\/login$/);
  await login(page, "tester_a");
  await page.getByRole("link", {name: "Ứng viên", exact: true}).click();
  await expect(page.getByRole("heading", {name: "22 ứng viên", exact: true})).toBeVisible();
  await page.getByRole("link", {name: "Ada Nguyen", exact: false}).click();
  await expect(page.getByRole("heading", {name: "Ada Nguyen", exact: true})).toBeVisible();
  await expect(page.getByRole("link", {name: "Soạn thư mời", exact: true})).toHaveCount(0);
  await expect(page.getByRole("link", {name: "System Ops", exact: true})).toHaveCount(0);
  await expect(page.getByRole("link", {name: "Tạo câu hỏi phỏng vấn", exact: true})).toHaveCount(0);
  await expect(page.getByLabel("Gán vị trí tuyển dụng", {exact: true})).toHaveCount(0);
  await page.goto("/candidates/33333333-3333-4333-8333-000000000023");
  await expect(page.getByRole("heading", {name: "Không tìm thấy ứng viên"})).toBeVisible();
  expect((await page.request.get("/api/backend/candidates")).status()).toBe(200);
  expect((await page.request.post(`/api/backend/candidates/${ada}/posting`, {headers: {origin}, data: {posting_id:null,expected_posting_id:null}})).status()).toBe(403);
  expect((await page.request.post("/api/backend/candidates", {headers: {origin}, data: {}})).status()).toBe(404);
  expect((await page.request.delete(`/api/backend/candidates/${ada}`, {headers: {origin}})).status()).toBe(404);
});

test("mobile navigation, profile layout and session revocation", async ({page, request}) => {
  await page.setViewportSize({width: 390, height: 844});
  await login(page); await page.goto("/candidates");
  await expect(page.getByRole("heading", {name: "23 ứng viên"})).toBeVisible();
  await page.getByRole("button", {name: "Mở điều hướng"}).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", {name: "Đóng điều hướng"}).click();
  await page.screenshot({path: "test-results/candidates-mobile.png", fullPage: true});
  await page.getByRole("link", {name: /Ada Nguyen/}).click();
  await expect(page.getByRole("heading", {name: "Ada Nguyen", exact: true})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({path: "test-results/candidate-profile-mobile.png", fullPage: true});
  await request.post(`${backend}/control/revoke`);
  await page.reload(); await expect(page).toHaveURL(/\/login\?reason=expired$/);
  await expect(page.getByRole("heading", {name: "Ada Nguyen", exact: true})).toHaveCount(0);
});

test("portrait is authenticated, appears below email and stays absent when unavailable", async ({page, request}) => {
  await login(page); await page.goto("/candidates");
  const portrait = page.getByRole("img", {name: "Ảnh chân dung Ada Nguyen", exact: true});
  await expect(portrait).toBeVisible();
  await expect.poll(() => portrait.evaluate(img => (img as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  const email = await page.getByText("ada@example.test", {exact: true}).boundingBox();
  const image = await portrait.boundingBox();
  expect(image!.y).toBeGreaterThan(email!.y + email!.height);
  const brokenPath = "/api/candidates/33333333-3333-4333-8333-000000000002/photo";
  await expect.poll(async () => (await (await request.get(`${backend}/control/calls`)).json()).some((c: {path: string}) => c.path === brokenPath)).toBe(true);
  await expect(page.getByRole("img", {name: "Ảnh chân dung Ứng viên 02", exact: true})).toHaveCount(0);
  await expect(page.getByRole("img", {name: "Ảnh chân dung Ứng viên 03", exact: true})).toHaveCount(0);
  const calls = await (await request.get(`${backend}/control/calls`)).json();
  expect(calls.some((c: {path: string}) => c.path === "/api/candidates/33333333-3333-4333-8333-000000000003/photo")).toBe(false);
  const response = await page.request.get(`/api/backend/candidates/${ada}/photo`);
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toBe("image/png");
  expect(response.headers()["cache-control"]).toContain("no-store");
  expect(response.headers()["x-content-type-options"]).toBe("nosniff");
  expect(response.headers()["x-request-id"]).toBe("portrait-request-id");
  expect((await response.body()).subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
  await page.screenshot({path: "test-results/candidates-portrait.png"});
  await request.post(`${backend}/control/mode`, {data: {mode: "photo-down"}});
  await page.reload();
  await expect(page.getByRole("heading", {name: "23 ứng viên"})).toBeVisible();
  await expect(portrait).toHaveCount(0);
  await expect(page.locator("#candidate-main [role=alert]")).toHaveCount(0);
});

test("portrait BFF allows scoped tester reads and rejects anonymous or non-image responses", async ({page, request}) => {
  const path = `/api/backend/candidates/${ada}/photo`;
  expect((await page.request.get(path)).status()).toBe(401);
  await login(page, "tester_a");
  expect((await page.request.get(path)).status()).toBe(200);
  expect((await page.request.post(path, {headers: {origin}, data: {}})).status()).toBe(404);
  await page.getByRole("button", {name: "Đăng xuất"}).first().click();
  await expect(page).toHaveURL(/\/login/);
  await login(page);
  await request.post(`${backend}/control/mode`, {data: {mode: "photo-bad"}});
  const bad = await page.request.get(path);
  expect(bad.status()).toBe(502);
  expect((await bad.json()).error.code).toBe("INVALID_BACKEND_RESPONSE");
});

test("profile portrait opens a keyboard accessible zoom viewer on desktop and mobile", async ({page}) => {
  await login(page); await page.goto(`/candidates/${ada}`);
  await expect(page.getByRole("heading", {name: "Ada Nguyen", exact: true})).toBeVisible();
  const trigger = page.getByRole("button", {name: "Phóng to ảnh chân dung Ada Nguyen", exact: true});
  await expect(trigger.getByRole("img")).toBeVisible();
  await trigger.click();
  const viewer = page.getByRole("dialog", {name: "Ảnh chân dung Ada Nguyen", exact: true});
  await expect(viewer).toBeVisible();
  await expect(viewer.getByRole("img", {name: "Ảnh phóng to của Ada Nguyen"})).toBeVisible();
  await expect(viewer.getByRole("button", {name: "Thu nhỏ ảnh", exact: true})).toBeDisabled();
  await viewer.getByRole("button", {name: "Phóng to ảnh", exact: true}).click();
  await expect(viewer.getByRole("status")).toHaveText("150%");
  await expect(viewer.locator(".portrait-canvas")).toHaveAttribute("style", /width: 150%; height: 150%/);
  await viewer.getByRole("button", {name: "Thu nhỏ ảnh", exact: true}).click();
  await expect(viewer.getByRole("status")).toHaveText("100%");
  for (let i = 0; i < 4; i++) await viewer.getByRole("button", {name: "Phóng to ảnh", exact: true}).click();
  await expect(viewer.getByRole("status")).toHaveText("300%");
  await expect(viewer.getByRole("button", {name: "Phóng to ảnh", exact: true})).toBeDisabled();
  await viewer.getByRole("button", {name: "Đặt lại kích thước ảnh"}).click();
  await expect(viewer.getByRole("status")).toHaveText("100%");
  await page.keyboard.press("Escape");
  await expect(viewer).not.toBeVisible();
  await expect(trigger).toBeFocused();
  await page.setViewportSize({width: 390, height: 844});
  await trigger.click();
  await expect(viewer).toBeVisible();
  expect(await viewer.evaluate(el => el.getBoundingClientRect().width <= window.innerWidth)).toBe(true);
  await viewer.getByRole("button", {name: "Đóng ảnh chân dung"}).click();
  await expect(viewer).not.toBeVisible();
  await trigger.click();
  await page.mouse.click(2, 2); // Backdrop.
  await expect(viewer).not.toBeVisible();
});

test("profile keeps initial avatar for missing portraits and list portraits can also zoom", async ({page}) => {
  await login(page);
  await page.goto("/candidates/33333333-3333-4333-8333-000000000002");
  await expect(page.getByRole("heading", {name: "Ứng viên 02", exact: true})).toBeVisible();
  await expect(page.locator(".profile-heading > .profile-avatar")).toBeVisible();
  await expect(page.getByRole("button", {name: /Phóng to ảnh chân dung/})).toHaveCount(0);
  await page.goto("/candidates/33333333-3333-4333-8333-000000000003");
  await expect(page.getByRole("heading", {name: "Ứng viên 03", exact: true})).toBeVisible();
  await expect(page.locator(".profile-heading > .profile-avatar")).toBeVisible();
  await expect(page.locator("#candidate-main").getByRole("img")).toHaveCount(0);
  await page.goto("/candidates");
  await page.getByRole("button", {name: "Phóng to ảnh chân dung Ada Nguyen", exact: true}).click();
  await expect(page.getByRole("dialog", {name: "Ảnh chân dung Ada Nguyen", exact: true})).toBeVisible();
});

test("refreshed workspace collapses navigation, expands skills and respects reduced motion", async ({page}) => {
  await page.setViewportSize({width:1440,height:1000});
  await page.emulateMedia({reducedMotion:"reduce"});
  await page.route("**/api/backend/candidates?*",async route=>{
    const response=await route.fetch();const body=await response.json();
    if(body.items?.[0])body.items[0].skills=["Python","SQL","Docker","Git","Airflow","Spark"];
    await route.fulfill({response,json:body});
  });
  await login(page);await page.goto("/candidates");
  await page.getByRole("button",{name:"+2 kỹ năng",exact:true}).click();
  await expect(page.getByText("Airflow",{exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Thu gọn",exact:true}).click();
  await expect(page.getByText("Airflow",{exact:true})).toHaveCount(0);
  await page.getByRole("button",{name:"Thu gọn thanh điều hướng",exact:true}).click();
  await expect(page.getByRole("button",{name:"Mở rộng thanh điều hướng",exact:true})).toHaveAttribute("aria-expanded","false");
  await expect(page.locator(".desktop-sidebar").getByRole("link",{name:"Ứng viên",exact:true})).toBeVisible();
  expect(await page.locator(".desktop-sidebar").evaluate(el=>el.getBoundingClientRect().width)).toBe(80);
  expect(await page.locator(".workspace").evaluate(el=>getComputedStyle(el).transitionDuration)).toBe("0s");
  await page.screenshot({path:"test-results/candidates-collapsed.png"});
  await page.getByRole("button",{name:"Mở rộng thanh điều hướng",exact:true}).click();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:"test-results/candidates-refresh-mobile.png"});
});
