"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CheckCircle2, Gamepad2, Gift, MailCheck, Wallet, X } from "lucide-react";
import { WALLET_EVENT, OPEN_WALLET_EVENT } from "./wallet-panel";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Order = { id: number; type: string; amount: string; status: string; method: string };
type Bonus = { email_verified: boolean; signup_available: boolean; kind: "signup" | "regular" | null; percent: number; signup_percent: number; regular_percent: number };

export const LAST_GAME_KEY = "jv-last-game";
const seenKey = (id: number) => `jv-seen-deposit-${id}`;
const safe = {
  get: (k: string) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
};

/**
 * When a deposit lands in the wallet (also after coming back from the payment page), tell the player the cash is theirs and
 * that the 50% / 10% bonuses are added to the GAME (not the wallet), with a button straight to the game.
 */
export function DepositSuccessPopup() {
  const { player } = useAuth();
  const [deposit, setDeposit] = useState<Order | null>(null);
  const [bonus, setBonus] = useState<Bonus | null>(null);
  const first = useRef(true);

  const check = useCallback(async () => {
    if (!player || document.hidden) return;
    try {
      const h = await api<{ orders: Order[] }>("/wallet/history");
      const paid = h.orders.filter((o) => o.type === "deposit" && o.status === "paid").sort((a, b) => b.id - a.id);
      const newest = paid[0];
      const stored = safe.get(seenKey(player.id));
      if (!newest) {  // nothing deposited yet: remember that, so the very first deposit is announced
        if (stored === null) safe.set(seenKey(player.id), "0");
        return;
      }
      if (stored === null && first.current) {  // first time on this device: do not announce old deposits
        safe.set(seenKey(player.id), String(newest.id));
        return;
      }
      if (newest.id > Number(stored ?? 0)) {
        safe.set(seenKey(player.id), String(newest.id));
        api<Bonus>("/cash-bonus").then(setBonus).catch(() => setBonus(null));
        setDeposit(newest);
      }
    } catch { /* wallet not available: nothing to announce */ } finally { first.current = false; }
  }, [player]);

  useEffect(() => {
    if (!player) return;
    check();
    const t = setInterval(check, 10000);
    window.addEventListener(WALLET_EVENT, check);
    return () => { clearInterval(t); window.removeEventListener(WALLET_EVENT, check); };
  }, [player, check]);

  useEffect(() => {
    if (!deposit) return;
    const close = () => setDeposit(null);
    window.addEventListener(OPEN_WALLET_EVENT, close);
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    document.addEventListener("keydown", onKey);
    return () => { window.removeEventListener(OPEN_WALLET_EVENT, close); document.removeEventListener("keydown", onKey); };
  }, [deposit]);

  if (!deposit || typeof document === "undefined") return null;
  const lastGame = safe.get(LAST_GAME_KEY);
  const href = lastGame ? `/game/${lastGame}?add=1` : "/games";
  const verified = bonus?.email_verified ?? false;
  const signupOpen = bonus?.signup_available ?? true;

  return createPortal(
    <div className="fixed inset-0 z-[80] grid place-items-center overflow-y-auto bg-black/75 p-4 backdrop-blur-sm" onMouseDown={(e) => { if (e.target === e.currentTarget) setDeposit(null); }}>
      <div role="dialog" aria-modal="true" aria-label="Deposit received" data-testid="deposit-success"
        className="relative my-auto w-full max-w-md overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-b from-[#1a1744] via-[#10152c] to-[#0b0f1e] p-6 text-white shadow-[0_30px_80px_rgba(0,0,0,0.7)]">
        <div className="pointer-events-none absolute -top-16 left-1/2 h-40 w-72 -translate-x-1/2 rounded-full bg-emerald-400/20 blur-3xl" />
        <button onClick={() => setDeposit(null)} aria-label="Close" className="absolute right-4 top-4 rounded-full p-1 text-white/60 hover:text-white"><X className="h-5 w-5" /></button>

        <div className="relative text-center">
          <span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-gradient-to-br from-emerald-300 to-emerald-500 text-slate-950 shadow-[0_8px_26px_rgba(52,211,153,0.45)]"><CheckCircle2 className="h-9 w-9" strokeWidth={2.2} /></span>
          <h3 className="mt-4 text-2xl font-black tracking-tight">Deposit received</h3>
          <p className="mt-1 text-sm text-slate-300"><b className="text-emerald-300">${Number(deposit.amount).toFixed(2)}</b> is now in your wallet.</p>
        </div>

        <div className="relative mt-5 rounded-2xl border border-[#ffd966]/30 bg-gradient-to-br from-[#ffd966]/12 to-transparent p-4">
          <div className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-[#f472d0] to-[#a21caf] text-white"><Gift className="h-4.5 w-4.5" /></span>
            <p className="text-sm font-black text-[#ffe9a8]">Your bonus goes to the game, not the wallet</p>
          </div>
          <ul className="mt-3 space-y-2 text-[13px] leading-snug text-slate-200">
            <li className="flex items-start gap-2"><span className="mt-0.5 rounded-full bg-[#ffd966]/20 px-2 py-0.5 text-[11px] font-black text-[#ffd966]">+{bonus?.signup_percent ?? 50}%</span><span><b>First add</b> to any one game (verified email). Added straight into your game.{!verified && signupOpen ? " Verify your email to unlock it." : !signupOpen ? " Already used." : ""}</span></li>
            <li className="flex items-start gap-2"><span className="mt-0.5 rounded-full bg-white/10 px-2 py-0.5 text-[11px] font-black text-slate-100">+{bonus?.regular_percent ?? 10}%</span><span><b>Every add</b> after that, straight into your game.</span></li>
          </ul>
          <p className="mt-3 text-[11px] text-slate-400">Add this cash to a game to receive the bonus. The wallet balance itself never receives it.</p>
        </div>

        <div className="relative mt-5 flex flex-col gap-2.5">
          <Link href={href} onClick={() => setDeposit(null)}
            className="inline-flex h-12 items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-[#38bdf8] to-[#4d8dff] font-black text-slate-950 shadow-[0_8px_22px_rgba(56,189,248,.3)] transition hover:brightness-110 active:scale-[0.98]">
            <Gamepad2 className="h-5 w-5" /> {lastGame ? "Go to my game & add cash" : "Choose a game & add cash"}
          </Link>
          {!verified && (
            <Link href="/dashboard" onClick={() => setDeposit(null)} className="inline-flex h-11 items-center justify-center gap-2 rounded-2xl border border-[#ffd966]/40 bg-[#ffd966]/10 text-sm font-bold text-[#ffd966] transition hover:bg-[#ffd966]/20">
              <MailCheck className="h-4 w-4" /> Verify email for the 50% bonus
            </Link>
          )}
          <button onClick={() => setDeposit(null)} className="inline-flex h-11 items-center justify-center gap-2 rounded-2xl border border-white/10 text-sm font-bold text-slate-300 transition hover:bg-white/10">
            <Wallet className="h-4 w-4" /> Maybe later
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
