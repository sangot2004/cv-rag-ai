import { NextRequest } from "next/server";
import { backendFetch, clearSession, connectionError, emptyResponse, forwardResponse, mutationGuard, SESSION_COOKIE } from "@/lib/server/backend";

export async function POST(request: NextRequest) {
  const rejected = mutationGuard(request);
  if (rejected) return rejected;
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  try {
    if (token) {
      const upstream = await backendFetch("/api/auth/logout", {method: "POST", token});
      // A revoked/expired session is already logged out. On outages retain the
      // cookie so the user can retry revoking the actual backend session.
      if (!upstream.ok && upstream.status !== 401) return await forwardResponse(upstream);
    }
    const response = emptyResponse();
    clearSession(response);
    return response;
  } catch (error) { return connectionError(error); }
}
