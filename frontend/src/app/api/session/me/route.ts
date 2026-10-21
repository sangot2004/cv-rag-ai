import { NextRequest } from "next/server";
import { userSchema } from "@/lib/contracts";
import { backendFetch, connectionError, errorResponse, forwardResponse, privateResponse, SESSION_COOKIE } from "@/lib/server/backend";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return errorResponse(401, "AUTHENTICATION_REQUIRED", "Vui lòng đăng nhập để tiếp tục.");
  try {
    const upstream = await backendFetch("/api/auth/me", {token});
    if (!upstream.ok) return await forwardResponse(upstream);
    const result = userSchema.safeParse(await upstream.json());
    return result.success ? privateResponse(result.data) : errorResponse(502, "INVALID_BACKEND_RESPONSE", "Không thể xác định tài khoản.");
  } catch (error) { return connectionError(error); }
}
