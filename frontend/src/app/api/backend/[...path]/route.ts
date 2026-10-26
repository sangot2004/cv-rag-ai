import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { threadIdSchema } from "@/lib/contracts";
import { backendFetch, connectionError, errorResponse, forwardResponse, mutationGuard, readJson, SESSION_COOKIE } from "@/lib/server/backend";

type Context = {params: Promise<{path: string[]}>};
function allowed(method: string, path: string[]) {
  if (path[0] === "ops") {
    if (path.length === 2) return method === "GET" && ["dashboard", "optimization"].includes(path[1]) || method === "POST" && path[1] === "optimization";
    if (path.length === 3 && path[1] === "optimization" && ["analyze", "defaults"].includes(path[2])) return method === "POST";
    return method === "POST" && path.length === 4 && z.uuid().safeParse(path[2]).success && (path[1] === "optimization" && ["experiment", "approve", "rollback"].includes(path[3]) || path[1] === "experiments" && path[3] === "recover");
  }
  if (path[0] === "admin") {
    if (path.length === 2 && ["departments", "postings", "users"].includes(path[1])) return method === "GET" || method === "POST";
    return path.length === 4 && path[1] === "users" && z.uuid().safeParse(path[2]).success && path[3] === "active" && method === "POST";
  }
  if (path[0] === "ingestion") {
    if (path.length === 2) return method === "GET" && ["capabilities", "jobs"].includes(path[1]);
    if (path[1] !== "jobs" || !z.uuid().safeParse(path[2]).success) return false;
    return path.length === 3 ? method === "GET" : path.length === 4 && path[3] === "retry" && method === "POST";
  }
  if (path[0] === "emails") {
    if (path[1] === "history") return method === "GET" && (path.length === 2 || (path.length === 3 && /^[1-9][0-9]*$/.test(path[2])));
    if (path[1] === "batches" && path.length === 2) return method === "GET" || method === "POST";
    if (!z.uuid().safeParse(path[2]).success) return false;
    if (path[1] === "batches") return (path.length === 3 && method === "GET") || (path.length === 4 && method === "POST" && ["dispatch", "requeue"].includes(path[3]));
    if (path[1] === "drafts") return method === "POST" && (path.length === 3 || (path.length === 4 && path[3] === "generate"));
    return path[1] === "deliveries" && path.length === 4 && method === "POST" && ["retry", "reconcile"].includes(path[3]);
  }
  if (path[0] === "candidates") {
    if (path.length === 1) return method === "GET";
    if (!z.uuid().safeParse(path[1]).success) return false;
    if (path.length === 2) return method === "GET";
    if (path.length === 3 && path[2] === "posting") return method === "POST";
    if (path.length === 3 && path[2] === "photo") return method === "GET";
    if (path[2] !== "interview-questions") return false;
    if (path.length === 3) return method === "GET" || method === "DELETE";
    return path.length === 4 && path[3] === "generate" && method === "POST";
  }
  if (path[0] !== "conversations") return false;
  if (path.length === 1) return method === "GET" || method === "POST";
  if (!threadIdSchema.safeParse(path[1]).success) return false;
  if (path.length === 2) return method === "DELETE";
  if (path.length !== 3) return false;
  if (method === "GET") return path[2] === "messages";
  return method === "POST" && ["messages", "resume", "feedback"].includes(path[2]);
}
async function proxy(request: NextRequest, context: Context) {
  const segments = (await context.params).path;
  const path = segments.join("/");
  if (!allowed(request.method, segments)) return errorResponse(404, "NOT_FOUND", "Không tìm thấy chức năng.");
  if (request.method !== "GET") {
    const rejected = mutationGuard(request);
    if (rejected) return rejected;
  }
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return errorResponse(401, "AUTHENTICATION_REQUIRED", "Vui lòng đăng nhập để tiếp tục.");
  let body: unknown;
  if (request.method === "POST") {
    try { body = await readJson(request); }
    catch { return errorResponse(422, "VALIDATION_ERROR", "Nội dung gửi lên không hợp lệ hoặc quá dài."); }
  }
  let query = "";
  if (path === "candidates" || (segments[0] === "emails" && request.method === "GET")) query = request.nextUrl.search;
  if (["admin", "ingestion", "ops"].includes(segments[0]) && request.method === "GET") query = request.nextUrl.search;
  if (segments[2] === "interview-questions" && request.method === "DELETE") query = request.nextUrl.search;
  if (path === "conversations" && request.method === "GET") {
    const limit = request.nextUrl.searchParams.get("limit") || "50";
    if (!/^[0-9]+$/.test(limit) || Number(limit) < 1 || Number(limit) > 50) return errorResponse(422, "VALIDATION_ERROR", "Số hội thoại phải từ 1 đến 50.");
    query = `?limit=${Number(limit)}`;
  }
  try {
    const upstream = await backendFetch(`/api/${path}${query}`, {method: request.method, token, body, timeout: 120_000});
    if (segments[0] === "candidates" && segments[2] === "photo" && upstream.ok) {
      const mediaType = upstream.headers.get("content-type")?.split(";")[0];
      if (upstream.status !== 200 || !mediaType || !["image/jpeg", "image/png", "image/webp"].includes(mediaType)) {
        await upstream.body?.cancel();
        return errorResponse(502, "INVALID_BACKEND_RESPONSE", "Máy chủ trả về ảnh không hợp lệ.");
      }
      return new NextResponse(upstream.body, {headers: {"Content-Type": mediaType,
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "X-Request-ID": upstream.headers.get("x-request-id") || crypto.randomUUID()}});
    }
    return await forwardResponse(upstream);
  } catch (error) { return connectionError(error); }
}
export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;
