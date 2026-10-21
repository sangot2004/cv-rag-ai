import { NextRequest } from "next/server";
import { loginSchema, tokenSchema } from "@/lib/contracts";
import { backendFetch, connectionError, cookieOptions, errorResponse, forwardResponse, mutationGuard, privateResponse, readJson, SESSION_COOKIE } from "@/lib/server/backend";

export async function POST(request: NextRequest) {
  const rejected = mutationGuard(request);
  if (rejected) return rejected;
  let input;
  try { input = loginSchema.parse(await readJson(request, 10_000)); }
  catch { return errorResponse(422, "VALIDATION_ERROR", "Hãy nhập tên đăng nhập và mật khẩu hợp lệ."); }
  try {
    const upstream = await backendFetch("/api/auth/login", {method: "POST", body: input});
    if (!upstream.ok) return await forwardResponse(upstream);
    const result = tokenSchema.safeParse(await upstream.json());
    if (!result.success) return errorResponse(502, "INVALID_BACKEND_RESPONSE", "Máy chủ trả về phiên đăng nhập không hợp lệ.");
    const session = result.data;
    const expires = new Date(Math.min(Date.parse(session.expires_at), Date.now() + session.expires_in * 1000));
    if (expires.getTime() <= Date.now()) return errorResponse(401, "AUTHENTICATION_REQUIRED", "Phiên đăng nhập đã hết hạn.");
    // Never return the bearer token in the browser-readable response.
    const response = privateResponse({user: session.user, expires_at: expires.toISOString()});
    response.cookies.set(SESSION_COOKIE, session.access_token, {...cookieOptions, expires});
    return response;
  } catch (error) { return connectionError(error); }
}
