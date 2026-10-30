"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Gem, Info, Sparkles, X } from "lucide-react";
import { Spinner } from "./ui/bits";
import { api } from "@/lib/api";

type LimitsInfo = {
  table: { deposit: string; min: string; max: string }[];
  note: string;
  bonus?: { table: { made: string; wallet: string }[]; note: string; min: string };
  facts: { min_deposit: string; max_redeem: string; min_wallet_cashout: string };
};

/**
 * The cashout rules, straight from the server's table (so the screen can never disagree with what is enforced).
 * Used right after a game login is created and from the wallet's Cashout tab.
 */
export function CashoutLimitsModal({ onDone, confirmLabel = "I Understand", lead = "Cashout", accent = "Limits" }: { onDone: () => void; confirmLabel?: string; lead?: string; accent?: string }) {
  const [info, setInfo] = useState<LimitsInfo | null>(null);
  const [failed, setFailed] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);
  useEffect(() => { api<LimitsInfo>("/cashout-rules").then(setInfo).catch(() => setFailed(true)); }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); onDone(); } };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [onDone]);

  if (!mounted) return null;
  return createPortal(
    <div data-modal-nested data-testid="limits-modal" role="dialog" aria-modal="true" aria-label={`${lead} ${accent}`}
      className="fixed inset-0 z-[90] grid place-items-center overflow-y-auto bg-black/75 p-4 backdrop-blur-md"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onDone(); }}>
      <div className="my-auto w-full max-w-md rounded-[1.9rem] bg-gradient-to-b from-[#A78BFA]/50 via-white/10 to-[#38BDF8]/40 p-px shadow-[0_30px_90px_rgba(76,29,149,0.45)]">
        <div className="relative overflow-hidden rounded-[1.85rem] bg-[#0A0E1B] p-5 text-white sm:p-6">
          <div className="pointer-events-none absolute -left-16 -top-16 h-52 w-52 rounded-full bg-[#7C3AED]/25 blur-3xl" aria-hidden />
          <div className="pointer-events-none absolute -bottom-20 -right-16 h-52 w-52 rounded-full bg-[#38BDF8]/15 blur-3xl" aria-hidden />

          <button onClick={onDone} aria-label="Close" className="absolute right-4 top-4 z-10 grid h-9 w-9 place-items-center rounded-full border border-white/10 bg-white/5 text-slate-400 transition hover:border-white/25 hover:text-white"><X className="h-4 w-4" /></button>

          <div className="relative flex items-center gap-3 pr-10">
            <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-[#8B5CF6] to-[#4F46E5] shadow-[0_8px_24px_rgba(124,58,237,0.5)] ring-1 ring-white/25"><Gem className="h-6 w-6" strokeWidth={1.8} /></span>
            <div>
              <h2 className="text-2xl font-black uppercase leading-none tracking-[0.1em]">{lead} <span className="bg-gradient-to-r from-[#C4B5FD] to-[#7DD3FC] bg-clip-text text-transparent">{accent}</span></h2>
              <p className="mt-1.5 text-xs text-slate-400">What you can take out of a game, set by the cash you add to it.</p>
            </div>
          </div>

          {failed ? (
            <p className="relative mt-6 rounded-2xl bg-white/5 p-4 text-sm text-slate-300">We couldn&apos;t load the rules right now. Please try again in a moment.</p>
          ) : !info ? (
            <div className="relative grid h-48 place-items-center"><Spinner className="h-6 w-6 text-sky-400" /></div>
          ) : (
            <div className="relative">
              <div className="mt-5 overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03]">
                <table className="w-full text-left" data-testid="limits-table">
                  <thead>
                    <tr className="bg-gradient-to-r from-[#1A1F3A] to-[#141A30] text-[11px] font-extrabold uppercase tracking-[0.14em] text-[#7DB4FF]">
                      <th className="px-4 py-3">Cash added</th><th className="px-3 py-3">Minimum</th><th className="px-3 py-3">Maximum</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm">
                    {info.table.map((row, i) => (
                      <tr key={row.deposit} className={`border-t border-white/[0.06] transition hover:bg-white/[0.05] ${i % 2 ? "bg-white/[0.015]" : ""}`}>
                        <td className="px-4 py-3.5 font-extrabold text-white">{row.deposit}</td>
                        <td className="px-3 py-3.5 font-semibold text-slate-300">{row.min}</td>
                        <td className="px-3 py-3.5 font-bold text-[#FCD34D]">{row.max}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-center text-[11px] text-slate-500">x3 and x12 mean 3 and 12 times the cash you added.</p>

              <div className="mt-4 grid grid-cols-3 gap-2.5">
                {([["Min deposit", info.facts.min_deposit], ["Max per cash out", info.facts.max_redeem], ["Min wallet cashout", info.facts.min_wallet_cashout]] as const).map(([label, value]) => (
                  <div key={label} className="rounded-2xl border border-white/10 bg-gradient-to-b from-white/[0.06] to-white/[0.02] px-2 py-3.5 text-center">
                    <p className="text-[10px] font-semibold uppercase leading-tight tracking-wider text-slate-400">{label}</p>
                    <p className="mt-1.5 bg-gradient-to-r from-[#67E8F9] to-[#38BDF8] bg-clip-text text-xl font-black text-transparent">{value}</p>
                  </div>
                ))}
              </div>

              {info.bonus && (
                <div className="mt-4 rounded-2xl border border-[#FCD34D]/25 bg-gradient-to-br from-[#FCD34D]/12 to-[#F59E0B]/5 p-4" data-testid="limits-bonus">
                  <p className="flex items-center gap-2 text-sm font-extrabold text-[#FDE68A]"><Sparkles className="h-4 w-4" />Bonus balance rule</p>
                  <p className="mt-1 text-xs text-[#FDE68A]/80">Play with bonus only? The game balance must reach {info.bonus.min} to cash out:</p>
                  <div className="mt-3 grid grid-cols-2 gap-2.5">
                    {info.bonus.table.map((t) => (
                      <div key={t.made} className="rounded-xl border border-white/10 bg-black/25 px-3 py-2.5 text-center">
                        <p className="text-[11px] font-semibold text-[#FDE68A]/70">{t.made}</p>
                        <p className="mt-0.5 text-base font-black text-emerald-300">{t.wallet} <span className="text-[11px] font-bold text-emerald-200/70">to wallet</span></p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-4 flex items-start gap-2.5 rounded-2xl border border-amber-400/25 bg-amber-400/[0.07] p-3.5 text-sm font-semibold text-amber-200">
                <Info className="mt-0.5 h-4 w-4 shrink-0" />
                <span>Winnings above the maximum are voided by the system.</span>
              </div>
            </div>
          )}

          <button onClick={onDone} data-testid="limits-understand"
            className="relative mt-5 h-12 w-full rounded-2xl bg-gradient-to-r from-[#3B82F6] via-[#6366F1] to-[#8B5CF6] text-base font-black text-white shadow-[0_10px_30px_rgba(99,102,241,0.45)] transition hover:brightness-110 active:scale-[0.98]">
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
