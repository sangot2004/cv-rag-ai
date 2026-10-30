import {expect, test, type Page} from "@playwright/test";

const backend = "http://127.0.0.1:28101";
const candidate = "33333333-3333-4333-8333-000000000001";
async function login(page: Page, username = "sang") {
  await page.goto("/login");
  await page.getByLabel("Tên đăng nhập", {exact:true}).fill(username);
  await page.getByLabel("Mật khẩu", {exact:true}).fill("test-password-123");
  await page.getByRole("button", {name:"Đăng nhập", exact:true}).click();
  await expect(page.getByRole("heading", {name:"Bắt đầu từ một câu hỏi"})).toBeVisible();
}
test.beforeEach(async ({request}) => {await request.post(`${backend}/control/reset`);});

for (const width of [360, 1440]) {
  test(`release screens fit ${width}px and keyboard navigation closes mobile menu`, async ({page}) => {
    test.setTimeout(60_000);
    await page.setViewportSize({width, height:900});
    await login(page);
    const failures: string[] = [];
    page.on("pageerror", error => failures.push(error.message));
    for (const path of ["/candidates", `/candidates/${candidate}`, `/interviews?candidate=${candidate}`,
      `/emails/compose?candidate=${candidate}`, "/emails/bulk", "/emails/history", "/emails/batches",
      "/ingestion/upload", "/ingestion/jobs", "/admin/users", "/admin/departments", "/admin/postings", "/ops"]) {
      await page.goto(path);
      await expect(page.locator(".workspace")).toBeVisible();
      await expect(page.locator(".loading-icon:visible, .content-skeleton:visible")).toHaveCount(0);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth), path).toBeTruthy();
    }
    if (width < 768) {
      await page.goto("/emails/compose");
      await page.getByRole("button", {name:"Mở điều hướng", exact:true}).click();
      const drawer = page.getByRole("dialog", {name:"Điều hướng", exact:true});
      const history = drawer.getByRole("link", {name:"Lịch sử gửi thư", exact:true});
      await history.focus(); await page.keyboard.press("Enter");
      await expect(page).toHaveURL(/\/emails\/history$/);
      await expect(drawer).not.toBeVisible();
    }
    expect(failures).toEqual([]);
  });
}

test("tester is denied every administration page even with direct URLs", async ({page}) => {
  await login(page, "tester_a");
  for (const path of ["/interviews", "/emails/compose", "/emails/bulk", "/emails/history", "/emails/batches",
    "/ingestion/upload", "/ingestion/jobs", "/admin/users", "/admin/departments", "/admin/postings", "/ops", "/ops/optimization"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", {name:"Bạn chưa có quyền truy cập", exact:true})).toBeVisible();
  }
});

test("invalid route has a Vietnamese recovery page on mobile", async ({page}) => {
  await page.setViewportSize({width:360, height:800});
  const response = await page.goto("/does-not-exist");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", {name:"Không tìm thấy trang", exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.getByRole("link", {name:"Trở về hội thoại", exact:true}).click();
  await expect(page).toHaveURL(/\/login$/);
});
