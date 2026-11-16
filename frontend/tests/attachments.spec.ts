import { test, expect, type Page } from "@playwright/test";

const backend = "http://127.0.0.1:28101";
type Call = { path: string; method: string; body: Record<string, unknown> };

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Tên đăng nhập", { exact: true }).fill("tester_a");
  await page.getByLabel("Mật khẩu", { exact: true }).fill("test-password-123");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Bắt đầu từ một câu hỏi" })).toBeVisible();
}
const pdf = (name: string) => ({
  name,
  mimeType: "application/pdf",
  buffer: Buffer.from("%PDF-1.4 fixture"),
});
const fileInput = (page: Page) => page.locator("input[type=file]");
const composerChips = (page: Page) => page.locator(".composer-box .attachment-chip");
async function calls(request: import("@playwright/test").APIRequestContext) {
  return (await (await request.get(`${backend}/control/calls`)).json()) as Call[];
}

test.beforeEach(async ({ request }) => {
  await request.post(`${backend}/control/reset`);
});

test("attach a PDF, send without text, history shows only the file chip", async ({
  page,
  request,
}) => {
  await login(page);
  await fileInput(page).setInputFiles(pdf("jd.pdf"));
  await expect(composerChips(page)).toHaveCount(1);
  await expect(composerChips(page).first()).toContainText("jd.pdf");
  // Sending is allowed with only an attachment (no typed question).
  const send = page.getByRole("button", { name: "Gửi câu hỏi" });
  await expect(send).toBeEnabled();
  await send.click();

  const userMessage = page.locator(".message.user");
  await expect(userMessage.locator(".attachment-chip")).toContainText("jd.pdf");
  await expect(userMessage).toContainText("Hãy phân tích tài liệu đính kèm");
  await expect(userMessage).not.toContainText("Nội dung giả lập");
  await expect(page.locator(".message.assistant")).toBeVisible();
  await expect(composerChips(page)).toHaveCount(0);

  const sent = (await calls(request)).find(
    (c) => c.path.endsWith("/messages") && c.method === "POST",
  );
  expect(sent?.body.question).toContain("--- Nội dung file 'jd.pdf' ---");
  expect(sent?.body.question).toContain("Nội dung giả lập của jd.pdf");
});

test("typed question is kept and attachment text is appended after it", async ({
  page,
  request,
}) => {
  await login(page);
  await page.getByLabel("Câu hỏi của bạn").fill("Đánh giá ứng viên theo JD này");
  await fileInput(page).setInputFiles([pdf("a.pdf"), pdf("b.pdf")]);
  await expect(composerChips(page)).toHaveCount(2);
  await page.getByRole("button", { name: "Gửi câu hỏi" }).click();
  await expect(page.locator(".message.user .attachment-chip")).toHaveCount(2);

  const sent = (await calls(request)).find((c) => c.path.endsWith("/messages"));
  expect(String(sent?.body.question).startsWith("Đánh giá ứng viên theo JD này\n\n")).toBe(true);
  expect(sent?.body.question).toContain("'a.pdf'");
  expect(sent?.body.question).toContain("'b.pdf'");
});

test("unsupported file type is rejected client-side without calling the backend", async ({
  page,
  request,
}) => {
  await login(page);
  await fileInput(page).setInputFiles({
    name: "resume.txt",
    mimeType: "application/octet-stream",
    buffer: Buffer.from("not supported"),
  });
  await expect(composerChips(page).first()).toContainText("Định dạng chưa hỗ trợ");
  // An errored chip must not count as sendable content.
  await expect(page.getByRole("button", { name: "Gửi câu hỏi" })).toBeDisabled();
  expect((await calls(request)).some((c) => c.path === "/api/attachments/extract")).toBe(false);
  await page.getByRole("button", { name: "Gỡ file resume.txt" }).click();
  await expect(composerChips(page)).toHaveCount(0);
});

test("backend extraction failure shows an error chip that can be removed", async ({
  page,
  request,
}) => {
  await request.post(`${backend}/control/mode`, { data: { mode: "attachment-error" } });
  await login(page);
  await fileInput(page).setInputFiles(pdf("scan.pdf"));
  await expect(composerChips(page).first()).toContainText("ATTACHMENT_UNREADABLE");
  await expect(page.getByRole("button", { name: "Gửi câu hỏi" })).toBeDisabled();
  // Typing a question still works; the failed file is simply not sent.
  await page.getByLabel("Câu hỏi của bạn").fill("Ứng viên nào biết Python?");
  await expect(page.getByRole("button", { name: "Gửi câu hỏi" })).toBeEnabled();
  await page.getByRole("button", { name: "Gỡ file scan.pdf" }).click();
  await expect(composerChips(page)).toHaveCount(0);
});

test("at most five attachments per message", async ({ page }) => {
  await login(page);
  await fileInput(page).setInputFiles(["1", "2", "3", "4", "5", "6"].map((n) => pdf(`f${n}.pdf`)));
  await expect(composerChips(page)).toHaveCount(5);
  await expect(page.getByRole("button", { name: "Đính kèm PDF/Word/ảnh" })).toBeDisabled();
});

test("Word .docx files are accepted and sent like PDFs", async ({ page, request }) => {
  await login(page);
  await fileInput(page).setInputFiles({
    name: "jd.docx",
    mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: Buffer.from("PK fixture"),
  });
  await expect(composerChips(page).first()).toContainText("jd.docx");
  await expect(composerChips(page).first()).not.toContainText("Định dạng chưa hỗ trợ");
  await page.getByRole("button", { name: "Gửi câu hỏi" }).click();
  await expect(page.locator(".message.user .attachment-chip")).toContainText("jd.docx");
  const sent = (await calls(request)).find((c) => c.path.endsWith("/messages"));
  expect(sent?.body.question).toContain("--- Nội dung file 'jd.docx' ---");
});
