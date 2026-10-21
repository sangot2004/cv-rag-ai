import "server-only";
import { NextRequest, NextResponse } from "next/server";

export const SESSION_COOKIE = process.env.NODE_ENV === "production" ? "__Host-cv_session" : "cv_session";
export const cookieOptions = {httpOnly: true, sameSite: "lax" as const, secure: process.env.NODE_ENV === "production", path: "/"};

export function privateResponse(body: unknown, status = 200, requestId = crypto.randomUUID()) {
  return NextResponse.json(body, {status, headers: {"Cache-Control": "private, no-store", "X-Request-ID": requestId}});
}
export function errorResponse(status: number, code: string, message: string, requestId?: string) {
  const id = requestId || crypto.randomUUID();
  const response = privateResponse({error: {code, message, request_id: id}}, status, id);
  if (status === 401) clearSession(response);
  return response;
}
export function clearSession(response: NextResponse) {
  response.cookies.set(SESSION_COOKIE, "", {...cookieOptions, maxAge: 0});
}
export function emptyResponse() {
  return new NextResponse(null, {status: 204, headers: {"Cache-Control": "private, no-store"}});
}

// All browser mutations must originate from this application, including login.
export function mutationGuard(request: NextRequest, mediaType = "application/json") {
  const expectedOrigin = process.env.APP_ORIGIN || new URL(request.url).origin;
  if (request.headers.get("origin") !== expectedOrigin || request.headers.get("sec-fetch-site") === "cross-site") {
    return errorResponse(403, "ORIGIN_REJECTED", "Yêu cầu không đến từ giao diện được phép.");
  }
  if (request.method !== "DELETE" && request.headers.get("content-type")?.split(";")[0].trim() !== mediaType) {
    return errorResponse(415, "UNSUPPORTED_MEDIA_TYPE", "Định dạng yêu cầu không hợp lệ.");
  }
}

export async function readBytes(request: Request, maxBytes: number) {
  // Enforce the limit even when Content-Length is missing or inaccurate.
  const reader = request.body?.getReader();
  if (!reader) throw new Error("INVALID_BODY");
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > maxBytes) { await reader.cancel(); throw new Error("INVALID_BODY"); }
      chunks.push(value);
    }
    return Buffer.concat(chunks);
  } finally { reader.releaseLock(); }
}

export async function readJson(request: Request, maxBytes = 100_000) {
  return JSON.parse((await readBytes(request, maxBytes)).toString("utf8")) as unknown;
}

export async function backendFetch(path: string, options: {method?: string; token?: string; body?: unknown; timeout?: number} = {}) {
  const base = new URL(process.env.API_INTERNAL_URL || "http://127.0.0.1:8000");
  if (!["http:", "https:"].includes(base.protocol) || base.username || base.password || base.pathname !== "/" || base.search || base.hash) {
    throw new Error("INVALID_API_CONFIGURATION");
  }
  const headers = new Headers({"Accept": "application/json", "X-Request-ID": crypto.randomUUID()});
  if (options.token) headers.set("Authorization", `Bearer ${options.token}`);
  const multipart = options.body instanceof FormData;
  if (options.body !== undefined && !multipart) headers.set("Content-Type", "application/json");
  return fetch(new URL(path, base), {
    method: options.method || "GET", headers, cache: "no-store", redirect: "error",
    body: options.body === undefined ? undefined : multipart ? options.body as FormData : JSON.stringify(options.body),
    signal: AbortSignal.timeout(options.timeout ?? 15_000),
  });
}

export async function forwardResponse(upstream: Response) {
  if (upstream.status === 204) return emptyResponse();
  const requestId = upstream.headers.get("x-request-id") || crypto.randomUUID();
  let data;
  try { data = await upstream.json(); }
  catch { return errorResponse(502, "INVALID_BACKEND_RESPONSE", "Máy chủ trả về dữ liệu không hợp lệ.", requestId); }
  if (!upstream.ok) {
    const code = typeof data?.error?.code === "string" ? data.error.code : "BACKEND_ERROR";
    const message = typeof data?.error?.message === "string" ? data.error.message : "Không thể hoàn tất yêu cầu.";
    return errorResponse(upstream.status, code, message, requestId);
  }
  return privateResponse(data, upstream.status, requestId);
}

export function connectionError(error: unknown) {
  const timeout = error instanceof Error && ["TimeoutError", "AbortError"].includes(error.name);
  return errorResponse(timeout ? 504 : 503, timeout ? "DEPENDENCY_TIMEOUT" : "DEPENDENCY_UNAVAILABLE",
    timeout ? "Máy chủ phản hồi quá thời gian chờ. Hãy kiểm tra trạng thái trước khi gửi lại." : "Chưa kết nối được máy chủ. Vui lòng thử lại sau.");
}
