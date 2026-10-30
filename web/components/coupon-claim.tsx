"use client";

import { useState } from "react";
import Link from "next/link";
import { Gift, Loader2 } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { notifyWalletChanged } from "./wallet-panel";

/** Redeem a coupon code. Codes are created by staff; each account can use a code once. The server decides everything. */
export function CouponClaim() {
  const { player } = useAuth();
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const redeem = async (e: React.FormEvent) => {
    e.preventDefault();
    const clean = code.trim().toUpperCase();
    if (!clean) { setError("Enter your coupon code."); return; }
    setLoading(true); setError(null); setSuccess(null);
    try {
      const r = await api<{ amount: string; bonus_balance: string }>("/coupons/redeem", { method: "POST", body: { code: clean } });
      setSuccess(`$${r.amount} bonus added. Your bonus balance is now $${r.bonus_balance}.`);
      setCode("");
      notifyWalletChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="container-x my-6 sm:my-8" aria-labelledby="coupon-title">
      <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-[#0B0F1C] p-5 sm:p-7 shadow-[0_15px_40px_rgba(0,0,0,0.5)]">
        <div className="pointer-events-none absolute -left-6 -top-6 h-36 w-36 rounded-3xl bg-fuchsia-600/15 blur-2xl" />
        <div className="pointer-events-none absolute -right-6 -bottom-6 h-40 w-40 rounded-3xl bg-fuchsia-500/15 blur-2xl" />

        <div className="relative z-10 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3 sm:gap-4">
            <div className="grid h-12 w-12 sm:h-14 sm:w-14 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-fuchsia-500 via-pink-600 to-purple-800 shadow-[0_8px_20px_rgba(217,70,239,0.4)] border border-white/20">
              <Gift className="h-6 w-6 text-white" />
            </div>
            <div>
              <h2 id="coupon-title" className="text-lg sm:text-2xl font-black text-white tracking-tight leading-tight">Have a coupon?</h2>
              <p className="mt-1 text-xs sm:text-sm text-slate-300 max-w-xl leading-relaxed">
                Enter your code to add bonus cash to your account instantly. Each code can be used once per account.
              </p>
            </div>
          </div>

          {player ? (
            <form onSubmit={redeem} className="flex w-full max-w-md items-center gap-2">
              <input
                type="text" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="COUPON CODE" aria-label="Coupon code"
                maxLength={30} autoComplete="off"
                className="h-12 flex-1 rounded-2xl border border-white/15 bg-[#13192B] px-4 text-xs sm:text-sm font-black tracking-wider text-white placeholder:text-slate-500 uppercase focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/20 transition"
              />
              <button type="submit" disabled={loading || !code.trim()}
                className="h-12 inline-flex shrink-0 items-center justify-center rounded-2xl bg-[#38bdf8] hover:bg-[#0ea5e9] disabled:opacity-50 text-slate-950 font-black px-6 text-xs sm:text-sm shadow-[0_6px_20px_rgba(56,189,248,0.4)] transition hover:scale-105 active:scale-95 whitespace-nowrap">
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Redeem"}
              </button>
            </form>
          ) : (
            <Link href="/login" className="inline-flex h-12 shrink-0 items-center justify-center rounded-2xl bg-[#38bdf8] px-6 text-sm font-black text-slate-950 transition hover:bg-[#0ea5e9]">Sign in to redeem</Link>
          )}
        </div>

        {error && <p role="alert" className="relative z-10 mt-4 rounded-2xl bg-red-500/15 p-3 text-sm text-red-200">{error}</p>}
        {success && <p role="status" data-testid="coupon-success" className="relative z-10 mt-4 rounded-2xl bg-emerald-500/15 p-3 text-sm text-emerald-100">{success}</p>}
      </div>
    </section>
  );
}
