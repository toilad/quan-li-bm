/**
 * Client for the Quản Lí BM backend (FastAPI). Every action in the UI goes through here —
 * failures come back as typed errors so the screen can say "Chưa cấu hình" / "Chưa khả dụng"
 * instead of showing a success that did not happen.
 */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type ApiErrorKind = "offline" | "unauthenticated" | "not_configured" | "not_available" | "conflict" | "invalid" | "error";

export class ApiError extends Error {
  constructor(
    public kind: ApiErrorKind,
    message: string,
    public status = 0,
    public missing: string[] = [],
    public reasons: string[] = [],
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    // credentials: the login session is an HttpOnly cookie set by the API
    res = await fetch(`${API_URL}${path}`, { cache: "no-store", credentials: "include", ...init });
  } catch {
    throw new ApiError("offline", "Không kết nối được backend — kiểm tra API đã chạy chưa");
  }
  const body = await res.json().catch(() => ({}));
  if (res.ok) return body as T;
  if (res.status === 401 && body?.status === "unauthenticated") {
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login"))
      window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
    throw new ApiError("unauthenticated", "Cần đăng nhập", 401);
  }
  const detail = body?.detail;
  const message = (typeof detail === "string" ? detail : detail?.message) || body?.message || `Lỗi ${res.status}`;
  const reasons: string[] = Array.isArray(detail?.reasons) ? detail.reasons : [];
  if (res.status === 503 && body?.status === "not_configured") throw new ApiError("not_configured", message, 503, body.missing ?? []);
  if (res.status === 501) throw new ApiError("not_available", message, 501);
  if (res.status === 409) throw new ApiError("conflict", message, 409);
  if (res.status === 422) throw new ApiError("invalid", message, 422, [], reasons);
  throw new ApiError("error", message, res.status);
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, json?: unknown) =>
    request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: json === undefined ? undefined : JSON.stringify(json) }),
  put: <T>(f: { name: string }, value: string) =>
    request<T>("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: f.name, value }) }),
  putJson: <T>(path: string, json: unknown) =>
    request<T>(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(json) }),
  patch: <T>(path: string, json: unknown) =>
    request<T>(path, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(json) }),
  upload: <T>(path: string, files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f, f.name));
    return request<T>(path, { method: "POST", body: fd });
  },
};

/* ───────── shared response types ───────── */

export type JobLog = { at: string; level: "ok" | "info" | "warn" | "err"; message: string };
export type Job = {
  id: number;
  kind: string;
  status: "queued" | "running" | "done" | "failed" | "blocked" | "conflict";
  step: string | null;
  attempts: number;
  error: string | null;
  payload: Record<string, unknown>;
  state: Record<string, unknown>;
  run_after: string | null;
  updated_at: string | null;
  logs?: JobLog[];
};

export type Status = {
  google: { sheets: { configured: boolean; missing: string[] }; drive: { configured: boolean; missing: string[] } };
  ai: { configured: boolean; model: string; missing: string[] };
  nicks: { id: string; name: string; inet_key: boolean; cpanel: { configured: boolean; missing: string[] } }[];
  unavailable: { what: string; why: string }[];
};

export const errorText = (e: unknown) => (e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e));
