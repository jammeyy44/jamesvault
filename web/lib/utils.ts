import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** The player's invite link, built from the site they are on right now, so it is always the real address. */
export function referralLink(code: string): string {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  return `${origin}/register?ref=${encodeURIComponent(code)}`;
}

/** Where to go after signing in or registering: the page they came from (?return=/game/x, same site only), otherwise the homepage. */
export function afterAuthPath(): string {
  if (typeof window === "undefined") return "/";
  const raw = new URLSearchParams(window.location.search).get("return") ?? "";
  const sameSite = raw.startsWith("/") && !raw.startsWith("//") && /^[A-Za-z0-9/_.?=&%-]*$/.test(raw);   // a path on this site only
  return sameSite && !raw.startsWith("/login") && !raw.startsWith("/register") ? raw : "/";
}

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso?: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function formatDay(iso?: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}
