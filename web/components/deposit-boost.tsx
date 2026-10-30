"use client";

import { useEffect, useRef, useState } from "react";
import { Flame } from "lucide-react";
import { cn } from "@/lib/utils";

export type Boost = { percent: number; expires_at: string; seconds_left: number };

/** Counts down from a server-provided `seconds_left` (anchored at receive time, so a wrong device clock cannot extend it). */
export function useCountdown(secondsLeft: number | undefined, onExpire?: () => void) {
  const endAt = useRef(0);
  const [left, setLeft] = useState(secondsLeft ?? 0);
  const fired = useRef(false);

  useEffect(() => {
    if (secondsLeft === undefined) return;
    endAt.current = Date.now() + secondsLeft * 1000;
    fired.current = false;
    setLeft(secondsLeft);
    const t = setInterval(() => {
      const s = Math.max(0, Math.round((endAt.current - Date.now()) / 1000));
      setLeft(s);
      if (s === 0 && !fired.current) { fired.current = true; onExpire?.(); }
    }, 1000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [secondsLeft]);

  const h = Math.floor(left / 3600), m = Math.floor((left % 3600) / 60), s = left % 60;
  return { left, h, m, s };
}

const two = (n: number) => String(n).padStart(2, "0");

/** "Deposit Boost +20%" strip with a live hh:mm:ss countdown. */
export function DepositBoostBanner({ boost, onExpire, className }: { boost: Boost; onExpire?: () => void; className?: string }) {
  const { left, h, m, s } = useCountdown(boost.seconds_left, onExpire);
  if (left <= 0) return null;
  return (
    <div role="status" aria-label={`Deposit Boost plus ${boost.percent} percent, ${h} hours ${m} minutes left`} data-testid="boost-banner"
      className={cn("flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-gradient-to-r from-[#0d1a3a] via-[#122451] to-[#1a2f6b] px-4 py-3 text-white shadow-[0_10px_30px_-14px_rgba(40,100,240,.7)]", className)}>
      <div className="flex min-w-0 items-start gap-3">
        <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-red-500/15 text-red-400"><Flame className="h-5 w-5" /></span>
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 text-lg font-extrabold leading-tight">
            Deposit Boost
            <span className="rounded-full bg-[#1f6bff] px-2.5 py-0.5 text-xs font-extrabold" data-testid="boost-percent">+{boost.percent}%</span>
          </p>
          <p className="mt-0.5 text-sm leading-snug text-white/70">Limited Boost: +{boost.percent}% on all deposits, hurry before it&apos;s gone</p>
        </div>
      </div>
      <div className="flex items-start gap-2" aria-hidden>
        {[["hh", h], ["mm", m], ["ss", s]].map(([label, v]) => (
          <div key={label as string} className="text-center">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-white/10 text-xl font-extrabold tabular-nums">{two(v as number)}</div>
            <div className="mt-1 text-xs font-semibold text-white/60">{label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
