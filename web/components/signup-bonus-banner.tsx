"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

function Gift({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="gb" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#f472d0" /><stop offset="1" stopColor="#a21caf" /></linearGradient>
      </defs>
      <path d="M32 6c-6 0-12 4-8 9 3 4 8 5 8 5s5-1 8-5c4-5-2-9-8-9z" fill="#d946ef" opacity=".9" />
      <rect x="8" y="22" width="48" height="12" rx="3" fill="url(#gb)" />
      <rect x="12" y="34" width="40" height="24" rx="3" fill="url(#gb)" opacity=".92" />
      <rect x="29" y="22" width="6" height="36" fill="#fbcfe8" opacity=".85" />
    </svg>
  );
}

/** Footer promo strip: the verified-email signup bonus. The button goes where the visitor needs to go next. */
export function SignupBonusBanner() {
  const { player } = useAuth();
  const href = !player ? "/register" : !player.email_verified ? "/dashboard" : "/games";
  const label = !player ? "Claim now" : !player.email_verified ? "Verify email" : "Add cash";
  return (
    <section aria-label="Signup bonus" data-testid="signup-bonus-banner"
      className="relative mb-10 overflow-hidden rounded-2xl border border-white/10 bg-[#0a0f1e] px-5 py-4 sm:px-7">
      <Gift className="pointer-events-none absolute -top-3 left-[44%] hidden h-20 w-20 rotate-12 opacity-20 blur-[2px] md:block" />
      <Gift className="pointer-events-none absolute -bottom-6 left-[70%] hidden h-24 w-24 -rotate-12 opacity-15 blur-[3px] md:block" />
      <div className="relative flex flex-col items-start gap-4 sm:flex-row sm:items-center">
        <Gift className="h-14 w-14 shrink-0 drop-shadow-[0_6px_14px_rgba(217,70,239,.45)] sm:h-16 sm:w-16" />
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-extrabold tracking-tight text-white sm:text-2xl">Get +50% on your first game add</h2>
          <p className="mt-0.5 text-sm text-slate-400">
            Verify your email and add cash to any one game: 50% bonus, then 10% on every add after that. Bonus goes straight into your game.
          </p>
        </div>
        <Link href={href} className="shrink-0 rounded-2xl bg-[#4dabff] px-8 py-3 text-sm font-extrabold text-white shadow-md transition hover:bg-[#3b9bf5] active:scale-95">
          {label}
        </Link>
      </div>
    </section>
  );
}
