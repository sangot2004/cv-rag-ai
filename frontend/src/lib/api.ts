export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string) { super(message); }
}
let leavingSession = false;
export function sessionNavigationPending() { return leavingSession; }
export function leaveSession(reason: "expired" | "signed-out") {
  if (leavingSession) return;
  leavingSession = true;
  window.location.replace(`/login?reason=${reason}`);
}

export async function api<T = unknown>(path: string, options: {method?: string; body?: unknown; signal?: AbortSignal; redirect401?: boolean} = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: options.method || "GET", credentials: "same-origin", cache: "no-store",
      headers: options.body === undefined ? undefined : {"Content-Type": "application/json"},
      body: options.body === undefined ? undefined : JSON.stringify(options.body), signal: options.signal,
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiError(0, "NETWORK_ERROR", "Mất kết nối. Yêu cầu có thể đã được xử lý; hãy kiểm tra trạng thái trước khi gửi lại.");
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    if (response.status === 401 && options.redirect401 !== false) leaveSession("expired");
    throw new ApiError(response.status, data?.error?.code || "HTTP_ERROR", data?.error?.message || "Không thể hoàn tất yêu cầu.", data?.error?.request_id || response.headers.get("x-request-id"));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function broadcastSession() {
  if (typeof BroadcastChannel !== "undefined") {
    const channel = new BroadcastChannel("cv-session");
    channel.postMessage("changed"); channel.close();
  }
}
