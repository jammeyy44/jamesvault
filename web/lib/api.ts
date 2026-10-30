/**
 * Thin client for the Flask API (proxied at /api/v1). Handles the CSRF handshake:
 * the token lives in the server session, is fetched lazily, and is replaced whenever the
 * server rotates the session (login, logout, password change/reset).
 */
export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) {
    super(message);
  }
}

let csrf: string | null = null;

async function ensureCsrf(force = false): Promise<string> {
  if (!csrf || force) {
    const res = await fetch("/api/v1/csrf", { credentials: "same-origin", cache: "no-store" });
    csrf = (await res.json()).csrf_token as string;
  }
  return csrf;
}

type Options = { method?: string; body?: unknown };

export async function api<T = any>(path: string, { method = "GET", body }: Options = {}, retry = true): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    headers["X-CSRF-Token"] = await ensureCsrf();
  }
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, {
      method,
      headers,
      credentials: "same-origin",
      cache: "no-store",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "We couldn't reach the server. Check your connection and try again.");
  }
  const data = await res.json().catch(() => ({}));
  if (res.status === 403 && /CSRF/i.test(data?.error ?? "") && retry) {
    await ensureCsrf(true);
    return api<T>(path, { method, body }, false);
  }
  if (!res.ok) throw new ApiError(res.status, data?.error ?? "Something went wrong.", data?.code);
  if (data?.csrf_token) csrf = data.csrf_token;
  return data as T;
}

/** Multipart upload (e.g. a game thumbnail). Same CSRF handshake; the browser sets the multipart Content-Type itself. */
export async function upload<T = any>(path: string, form: FormData, retry = true): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, { method: "POST", headers: { Accept: "application/json", "X-CSRF-Token": await ensureCsrf() }, credentials: "same-origin", body: form });
  } catch {
    throw new ApiError(0, "We couldn't reach the server. Check your connection and try again.");
  }
  const data = await res.json().catch(() => ({}));
  if (res.status === 403 && /CSRF/i.test(data?.error ?? "") && retry) { await ensureCsrf(true); return upload<T>(path, form, false); }
  if (!res.ok) throw new ApiError(res.status, data?.error ?? "Something went wrong.", data?.code);
  return data as T;
}

export const errorMessage = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");

// ---- shared types
export type Game = {
  id: number; slug: string; name: string; provider: string | null; provider_id: number | null;
  category: string; image_url: string | null; download_url?: string | null; description: string | null; status: string;
  is_featured: boolean; is_new: boolean; launch_supported: boolean; favorite?: boolean;
};
export type Promotion = {
  id: number; slug: string; title: string; promo_type: string; description: string | null;
  eligibility: string | null; reward_details: string | null; terms: string | null; image_url: string | null;
  claim_rule: string; repeat: string; starts_at: string | null; ends_at: string | null; state: string;
  claimed: boolean; can_claim: boolean; claim_blocked_reason: string | null; requires_coupon: boolean;
};
export type Role = "player" | "support" | "content" | "superadmin";
export type Player = { id: number; username: string; email: string; referral_code: string; email_verified: boolean; role: Role; is_admin: boolean };
