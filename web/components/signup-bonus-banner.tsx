"use client";

import Link from "next/link";
import { useId } from "react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

function Gift({ className }: { className?: string }) {
  const id = useId().replace(/:/g, "");  // every copy needs its own gradient id, or hidden copies break the visible one
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={`gb${id}`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#f472d0" /><stop offset="1" stopColor="#a21caf" /></linearGradient>
      </defs>
      <path d="M32 8c-7 0-13 5-8 10 3 3 8 4 8 4s5-1 8-4c5-5-1-10-8-10z" fill="#e879f9" />
      <rect x="6" y="22" width="52" height="13" rx="3.5" fill={`url(#gb${id})`} />
      <rect x="10" y="35" width="44" height="24" rx="3.5" fill={`url(#gb${id})`} opacity=".92" />
      <rect x="28.5" y="22" width="7" height="37" fill="#fbcfe8" opacity=".9" />
    </svg>
  );
}

/** Footer promo strip: the signup bonus. Stacked on phones (icon + headline, text, full-width button), one row on larger screens. */
export function SignupBonusBanner() {
  const { player } = useAuth();
  const href = !player ? "/register" : !player.email_verified ? "/dashboard" : "/games";
  const label = !player ? "Claim now" : !player.email_verified ? "Verify email" : "Add cash";
  return (
    <section aria-label="Signup bonus" data-testid="signup-bonus-banner"
      className="relative mb-8 overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-[#1a1340] via-[#0d1226] to-[#0a0f1e] p-4 sm:mb-10 sm:px-7 sm:py-4">
      <div className="pointer-events-none absolute -left-10 -top-12 h-36 w-36 rounded-full bg-fuchsia-500/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-12 right-10 h-32 w-32 rounded-full bg-sky-400/10 blur-3xl" />
      <Gift className="pointer-events-none absolute -top-3 left-[44%] hidden h-20 w-20 rotate-12 opacity-20 blur-[2px] md:block" />
      <Gift className="pointer-events-none absolute -bottom-6 left-[70%] hidden h-24 w-24 -rotate-12 opacity-15 blur-[3px] md:block" />

      <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="flex items-center gap-3.5 sm:flex-1">
          <Gift className="h-14 w-14 shrink-0 drop-shadow-[0_6px_14px_rgba(217,70,239,.5)] sm:h-16 sm:w-16" />
          <div className="min-w-0">
            <h2 className="text-lg font-black leading-tight tracking-tight text-white sm:text-2xl">Get +50% on your first game add</h2>
            <p className="mt-1 hidden text-sm text-slate-400 sm:block">
              Verify your email and add cash to any one game: 50% bonus, then 10% on every add after that. Bonus goes straight into your game.
            </p>
          </div>
        </div>

        <p className="text-[13px] leading-snug text-slate-400 sm:hidden">
          Verify your email and add cash to any one game: <b className="text-slate-200">50% bonus</b>, then <b className="text-slate-200">10%</b> on every add after that. Bonus goes straight into your game.
        </p>

        <Link href={href}
          className={cn("inline-flex h-12 w-full shrink-0 items-center justify-center rounded-2xl bg-gradient-to-r from-[#38bdf8] to-[#4d8dff] px-8 text-sm font-extrabold text-white shadow-[0_8px_22px_rgba(56,189,248,.3)] transition hover:brightness-110 active:scale-[0.98] sm:h-11 sm:w-auto")}>
          {label}
        </Link>
      </div>
    </section>
  );
}
