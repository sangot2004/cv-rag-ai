import { NextRequest } from "next/server";
import { z } from "zod";
import { backendFetch, connectionError, errorResponse, forwardResponse, mutationGuard, readBytes, SESSION_COOKIE } from "@/lib/server/backend";

export async function POST(request: NextRequest) {
  const rejected = mutationGuard(request, "multipart/form-data");
  if (rejected) return rejected;
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return errorResponse(401, "AUTHENTICATION_REQUIRED", "Vui lòng đăng nhập để tiếp tục.");
  // Check the role before accepting a potentially large body. FastAPI repeats
  // authorization after upload; the browser never receives the session token.
  try {
    const identity = await backendFetch("/api/auth/me", {token});
    if (!identity.ok) return forwardResponse(identity);
    const user = await identity.json();
    if (user.role !== "admin") return errorResponse(403, "FORBIDDEN", "Chức năng này chỉ dành cho admin.");
  } catch (error) {return connectionError(error);}
  let form: FormData;
  try {
    const bytes = await readBytes(request, 50 * 1024 * 1024 + 65536);
    form = await new Response(new Uint8Array(bytes), {headers: {"Content-Type": request.headers.get("content-type")!}}).formData();
  } catch {return errorResponse(413, "UPLOAD_BODY_INVALID", "File quá lớn hoặc dữ liệu upload không hợp lệ.");}
  const file = form.get("file"), posting = form.get("posting_id");
  if ([...form.keys()].length !== 2 || !(file instanceof File) || !z.uuid().safeParse(posting).success || file.size > 50 * 1024 * 1024) {
    return errorResponse(422, "VALIDATION_ERROR", "Cần một file PDF và vị trí tuyển dụng hợp lệ.");
  }
  try {return await forwardResponse(await backendFetch("/api/ingestion/uploads", {method: "POST", token, body: form, timeout: 120000}));}
  catch (error) {return connectionError(error);}
}
