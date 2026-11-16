import { NextRequest } from "next/server";
import {
  backendFetch,
  connectionError,
  errorResponse,
  forwardResponse,
  mutationGuard,
  readBytes,
  SESSION_COOKIE,
} from "@/lib/server/backend";

const MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024;

export async function POST(request: NextRequest) {
  const rejected = mutationGuard(request, "multipart/form-data");
  if (rejected) return rejected;
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token)
    return errorResponse(401, "AUTHENTICATION_REQUIRED", "Vui lòng đăng nhập để tiếp tục.");
  let form: FormData;
  try {
    const bytes = await readBytes(request, MAX_ATTACHMENT_BYTES + 65536);
    form = await new Response(new Uint8Array(bytes), {
      headers: { "Content-Type": request.headers.get("content-type")! },
    }).formData();
  } catch {
    return errorResponse(
      413,
      "ATTACHMENT_TOO_LARGE",
      "File quá lớn hoặc dữ liệu upload không hợp lệ.",
    );
  }
  const file = form.get("file");
  if ([...form.keys()].length !== 1 || !(file instanceof File) || file.size === 0) {
    return errorResponse(422, "FILE_REQUIRED", "Cần đính kèm một file.");
  }
  if (file.size > MAX_ATTACHMENT_BYTES) {
    return errorResponse(
      413,
      "ATTACHMENT_TOO_LARGE",
      "File vượt quá dung lượng cho phép (tối đa 15MB).",
    );
  }
  try {
    return await forwardResponse(
      await backendFetch("/api/attachments/extract", {
        method: "POST",
        token,
        body: form,
        timeout: 60000,
      }),
    );
  } catch (error) {
    return connectionError(error);
  }
}
