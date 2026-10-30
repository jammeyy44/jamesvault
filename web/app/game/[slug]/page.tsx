"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, Check, Copy, Eye, EyeOff, FileText, FlaskConical, Gift, Info,
  KeyRound, Pencil, Play, RefreshCw, Sparkles, Trash2, X
} from "lucide-react";
import { api, ApiError, errorMessage, type Game } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Spinner } from "@/components/ui/bits";
import { OPEN_WALLET_EVENT, notifyWalletChanged } from "@/components/wallet-panel";
import { TiredOfLosingCard } from "@/components/free-spin-modal";
import { TestYourLuckBanner } from "@/components/test-your-luck";
import { cn } from "@/lib/utils";

type Access = {
  mode: "sandbox" | "live" | "disabled";
  game: { slug: string; name: string; category: string; image_url: string | null; download_url?: string | null; status: string };
  account: { username: string } | null;
  cash_enabled: boolean;
  cash: { min: string; max: string; quick: number[]; cashout_min: string | null; cashout_max: string | null };
  sandbox_notice: string | null;
  cash_notice: string | null;
  wallet_funded?: boolean;
  wallet_balance?: string | null;
  bonus_enabled?: boolean;
  bonus_balance?: string | null;
  bonus_min?: string;
};

type CashResult = { status: string; sandbox: boolean; amount: string; note: string | null; source?: "wallet" | "bonus"; reason?: string };
type LimitsInfo = { table: { deposit: string; min: string; max: string }[]; note: string; bonus?: { table: { made: string; wallet: string }[]; note: string; min: string }; facts: { min_deposit: string; max_redeem: string; min_wallet_cashout: string } };

/** Shown once, right after a login is created: the cashout rules, straight from the server's table. */
function CashoutLimitsModal({ onDone }: { onDone: () => void }) {
  const [info, setInfo] = useState<LimitsInfo | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { api<LimitsInfo>("/cashout-rules").then(setInfo).catch(() => setFailed(true)); }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onDone(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onDone]);

  return (
    <div className="fixed inset-0 z-[60] grid place-items-center overflow-y-auto bg-black/80 p-4 backdrop-blur-md" role="dialog" aria-modal="true" aria-label="Cashout limits" data-testid="limits-modal">
      <div className="relative my-auto w-full max-w-md rounded-3xl border border-white/10 bg-[#0B0F1A] p-5 text-white shadow-[0_30px_80px_rgba(0,0,0,0.7)] sm:p-6">
        <button onClick={onDone} aria-label="Close" className="absolute right-4 top-4 grid h-9 w-9 place-items-center rounded-full border border-white/10 bg-white/5 text-slate-400 transition hover:text-white"><X className="h-4 w-4" /></button>
        <h2 className="px-8 text-center text-2xl font-black uppercase tracking-[0.12em] sm:text-3xl">Cashout <span className="text-[#A78BFA]">Limits</span></h2>

        {failed ? (
          <p className="mt-6 rounded-2xl bg-white/5 p-4 text-sm text-slate-300">We couldn&apos;t load the limits right now. You can see them any time on the Cash Out screen.</p>
        ) : !info ? (
          <div className="grid h-48 place-items-center"><Spinner className="h-6 w-6 text-sky-400" /></div>
        ) : (
          <>
            <div className="mt-5 overflow-hidden rounded-2xl border border-white/10">
              <table className="w-full text-left" data-testid="limits-table">
                <thead className="bg-[#121826] text-xs font-extrabold uppercase tracking-wider text-blue-400">
                  <tr><th className="px-4 py-3">Deposit</th><th className="px-3 py-3">Minimum</th><th className="px-3 py-3">Maximum</th></tr>
                </thead>
                <tbody className="text-sm">
                  {info.table.map((row) => (
                    <tr key={row.deposit} className="border-t border-white/[0.06]">
                      <td className="px-4 py-3.5 font-bold text-white">{row.deposit}</td>
                      <td className="px-3 py-3.5 font-semibold text-slate-300">{row.min}</td>
                      <td className="px-3 py-3.5 font-semibold text-slate-300">{row.max}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-2.5">
              {([["Min deposit", info.facts.min_deposit], ["Max per redeem", info.facts.max_redeem], ["Min wallet cashout", info.facts.min_wallet_cashout]] as const).map(([label, value]) => (
                <div key={label} className="rounded-2xl border border-white/10 bg-white/[0.03] px-2 py-3 text-center">
                  <p className="text-[10px] font-semibold uppercase leading-tight tracking-wider text-slate-400">{label}</p>
                  <p className="mt-1.5 text-lg font-extrabold text-cyan-300">{value}</p>
                </div>
              ))}
            </div>

            {info.bonus && (
              <div className="mt-4 rounded-2xl border border-[#ffd966]/30 bg-[#ffd966]/10 p-3.5 text-sm text-[#ffd966]" data-testid="limits-bonus">
                <p className="font-bold">Bonus balance rule</p>
                <p className="mt-1 text-xs text-[#ffd966]/90">If you play with bonus only, your game balance must reach {info.bonus.min} to cash out:</p>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {info.bonus.table.map((t) => (
                    <div key={t.made} className="rounded-xl bg-black/20 px-3 py-2 text-center">
                      <p className="text-[11px] text-[#ffd966]/70">{t.made}</p>
                      <p className="text-base font-extrabold text-emerald-300">{t.wallet} to wallet</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="mt-4 flex items-start gap-2.5 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-3.5 text-sm font-semibold text-amber-300">
              <Info className="mt-0.5 h-4 w-4 shrink-0" />
              <span>NOTE: {info.note.replace(/^Winning amount/i, "winning").replace(/\.$/, "")}.</span>
            </div>
            <p className="mt-2 text-center text-[11px] text-slate-500">x3 / x12 mean 3 / 12 times the cash you added.</p>
          </>
        )}

        <button onClick={onDone} data-testid="limits-understand" className="mt-4 h-12 w-full rounded-2xl bg-gradient-to-r from-[#3B82F6] to-[#8B5CF6] text-base font-black text-white shadow-lg transition hover:brightness-110 active:scale-[0.98]">I Understand</button>
      </div>
    </div>
  );
}

type RedeemPreview = {
  table: { deposit: string; min: string; max: string }[]; note: string; sandbox: boolean; latest_deposit: string | null;
  rule: { row: number; deposit: string; min: string; max: string } | null; game_balance: string | null; payout: string | null;
  voided: string | null; can_redeem: boolean; needs_confirm: boolean; reason: string | null;
  added?: { cash: string; bonus: string; session: string };
  mode?: "cash" | "bonus";
  bonus_rule?: { table: { made: string; wallet: string }[]; min: string; note: string };
};
type RedeemResult = { status: string; payout: string; voided: string; note: string | null };

const DEFAULT_COVERS: Record<string, string> = {
  "royal-vault": "/images/game_royal_vault.jpg",
  "estar": "/images/game_estar.jpg",
  "royal-treasure": "/images/game_royal_treasure.jpg",
  "yolo-lucky-wheel": "/images/game_yolo_wheel.jpg",
  "vblink": "/images/game_vblink.jpg",
  "game-vault": "/images/game_royal_vault.jpg",
};

function getGameCover(game: { slug?: string; name: string; image_url: string | null }) {
  if (game.image_url) return game.image_url;
  if (game.slug && DEFAULT_COVERS[game.slug]) return DEFAULT_COVERS[game.slug];
  const slug = game.name.toLowerCase().replace(/[^a-z0-9]/g, "-");
  for (const k of Object.keys(DEFAULT_COVERS)) {
    if (slug.includes(k) || k.includes(slug)) return DEFAULT_COVERS[k];
  }
  return DEFAULT_COVERS["royal-vault"];
}

const num = (v?: string | null) => Number(v ?? 0);
const money = (v: string | number) => `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: Number.isInteger(Number(v)) ? 0 : 2, maximumFractionDigits: 2 })}`;
const money2 = (v: string | number) => `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function FullscreenGamePage() {
  const params = useParams();
  const router = useRouter();
  const { player } = useAuth();
  const slug = (params?.slug as string) || "game-vault";

  const [step, setStep] = useState<"dashboard" | "cash" | "redeem">("dashboard");
  const [access, setAccess] = useState<Access | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [balance, setBalance] = useState<{ amount: string; at: string } | null>(null);
  const [balanceError, setBalanceError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showCredsModal, setShowCredsModal] = useState(false);
  const [showLimits, setShowLimits] = useState(false);
  const [creds, setCreds] = useState<{ username: string; password: string } | null>(null);
  const [credError, setCredError] = useState<string | null>(null);
  const [showPass, setShowPass] = useState(false);
  const [copiedPass, setCopiedPass] = useState(false);
  const [confirming, setConfirming] = useState<"reset" | "remove" | null>(null);
  const [working, setWorking] = useState(false);
  const [note, setNote] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const loadCreds = useCallback(() => {
    api<{ username: string; password: string }>(`/games/${slug}/access/credentials`)
      .then((c) => { setCreds(c); setCredError(null); })
      .catch((e) => setCredError(errorMessage(e)));
  }, [slug]);

  const copyPassword = async () => {
    if (!creds) return;
    try { await navigator.clipboard.writeText(creds.password); setCopiedPass(true); setTimeout(() => setCopiedPass(false), 2000); } catch { /* clipboard */ }
  };

  const resetPassword = async () => {
    setWorking(true); setNote(null);
    try {
      await api(`/games/${slug}/access/reset-password`, { method: "POST" });
      setConfirming(null);
      setShowPass(true); loadCreds();   // the new password appears right in the fields below
      setNote({ tone: "ok", text: "Your password was changed." });
    } catch (e) { setNote({ tone: "error", text: errorMessage(e) }); } finally { setWorking(false); }
  };
  const removeLogin = async () => {
    setWorking(true); setNote(null);
    try {
      await api(`/games/${slug}/access`, { method: "DELETE" });
      setConfirming(null); setBalance(null); setShowCredsModal(false);
      await loadAccess();
    } catch (e) { setConfirming(null); setNote({ tone: "error", text: errorMessage(e) }); } finally { setWorking(false); }
  };

  // Fast pre-fill with optimistic game info to open instantly
  const displayName = slug.split("-").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  const fallbackGame = {
    slug,
    name: displayName,
    category: "Slots, Table Games",
    image_url: DEFAULT_COVERS[slug] || "/images/game_royal_vault.jpg",
    status: "active",
  };

  const loadAccess = useCallback(async () => {
    try {
      const res = await api<Access>(`/games/${slug}/access`);
      setAccess(res);
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [slug]);

  const refreshBalance = useCallback(async () => {
    setRefreshing(true);
    setBalanceError(null);
    try {
      const r = await api<{ balance: string; as_of: string }>(`/games/${slug}/balance`);
      setBalance({ amount: r.balance, at: r.as_of });
    } catch (e) {
      setBalance(null);
      setBalanceError(errorMessage(e));
    } finally {
      setRefreshing(false);
    }
  }, [slug]);

  useEffect(() => {
    loadAccess();
  }, [loadAccess]);

  useEffect(() => {
    if (access?.account) {
      refreshBalance();
      loadCreds();
    } else {
      setCreds(null); setShowPass(false);
    }
  }, [access?.account, refreshBalance, loadCreds]);

  const handleGetAccess = async () => {
    if (!player) {
      router.push(`/login?return=/game/${slug}`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api<Access>(`/games/${slug}/access`, { method: "POST" });
      setAccess(res);
      setShowLimits(true); // the cashout limits come first; "I Understand" then opens the login details
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const copyUsername = async (u: string) => {
    try {
      await navigator.clipboard.writeText(u);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard */ }
  };

  const currentGame = access?.game || fallbackGame;
  const coverUrl = getGameCover(currentGame);
  const hasAccount = !!access?.account;

  return (
    <div className="min-h-screen bg-[#070A12] text-white flex flex-col pb-16">
      
      {/* Top Header Bar matching user's screenshot */}
      <div className="sticky top-0 z-30 border-b border-white/10 bg-[#0c101c]/95 backdrop-blur-md px-4 sm:px-8 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="grid h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
          <h1 className="text-sm font-black uppercase tracking-wider text-slate-200">
            {currentGame.name}
          </h1>
        </div>

        <button
          onClick={() => router.push("/games")}
          aria-label="Close and return to games"
          className="grid h-9 w-9 place-items-center rounded-xl border border-white/10 bg-white/5 text-slate-400 hover:text-white hover:bg-white/10 transition">
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Main Fullscreen Body */}
      <div className="container-x w-full max-w-6xl py-6 sm:py-8 flex-1">
        
        {step === "dashboard" && (
          <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6 items-start">
            
            {/* LEFT COLUMN: Game Profile Card (Screenshots 1, 2, 3) */}
            <div className="rounded-3xl border border-white/10 bg-[#121829] p-5 sm:p-7 shadow-2xl flex flex-col">
              
              {/* Full-bleed game artwork poster */}
              <div className="relative aspect-[4/3] w-full overflow-hidden rounded-2xl bg-slate-900 border border-white/10 shadow-lg">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={coverUrl}
                  alt={currentGame.name}
                  className="h-full w-full object-cover transition-transform duration-500 hover:scale-105"
                />
              </div>

              {/* Title row with Mint Green circular play button */}
              <div className="mt-5 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-2xl font-black text-white tracking-tight truncate">
                    {currentGame.name}
                  </h2>
                  <p className="text-xs text-slate-400 font-semibold truncate mt-0.5">
                    {currentGame.category || "Slots, Table Games"}
                  </p>
                </div>

                <button
                  onClick={hasAccount ? () => setShowCredsModal(true) : handleGetAccess}
                  aria-label="Play game"
                  className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-emerald-400 hover:bg-emerald-300 text-slate-950 font-black shadow-[0_4px_20px_rgba(52,211,153,0.5)] transition hover:scale-105 active:scale-95">
                  <Play className="h-5 w-5 fill-current ml-0.5" />
                </button>
              </div>

              <hr className="my-5 border-white/10" />

              {/* State A: User does NOT have an account yet (Exact match for Screenshot 3) */}
              {!hasAccount && (
                <div className="space-y-4">
                  {/* Blue info notice box */}
                  <div className="flex items-center gap-3 rounded-2xl border border-sky-400/25 bg-sky-500/15 p-4 text-xs sm:text-sm text-sky-200">
                    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-sky-400 text-slate-950 text-xs font-black">
                      i
                    </span>
                    <span>
                      {busy
                        ? "Your login request is being executed.."
                        : "You don't have an account, get your access right now"}
                    </span>
                  </div>

                  {error && (
                    <p role="alert" className="rounded-2xl bg-rose-500/15 border border-rose-500/20 p-3 text-xs text-rose-200">
                      {error}
                    </p>
                  )}

                  {/* Sky blue Get access button with animated loading dots */}
                  <button
                    onClick={handleGetAccess}
                    disabled={busy}
                    className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-[#38bdf8] hover:bg-[#0ea5e9] text-slate-950 font-black text-sm transition hover:scale-[1.02] active:scale-95 disabled:opacity-60 shadow-[0_8px_25px_rgba(56,189,248,0.4)]">
                    {busy ? (
                      <span className="flex items-center gap-1.5 py-1">
                        <span className="h-2 w-2 rounded-full bg-slate-950 animate-bounce" />
                        <span className="h-2 w-2 rounded-full bg-slate-950 animate-bounce [animation-delay:0.15s]" />
                        <span className="h-2 w-2 rounded-full bg-slate-950 animate-bounce [animation-delay:0.3s]" />
                      </span>
                    ) : (
                      <>
                        <KeyRound className="h-4 w-4" /> Get access
                      </>
                    )}
                  </button>
                </div>
              )}

              {/* State B: User HAS an account (Exact match for Screenshots 1 & 2) */}
              {hasAccount && (
                <div className="space-y-4">
                  {/* Balance section */}
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-3xl font-black text-white tabular-nums tracking-tight">
                        {balance ? money2(balance.amount) : "$0.00"}
                      </p>
                      <p className="text-xs text-slate-400 font-semibold mt-0.5">Balance</p>
                    </div>

                    <button
                      onClick={refreshBalance}
                      aria-label="Refresh balance"
                      className="flex items-center gap-2 text-right text-xs text-slate-400 hover:text-white transition group">
                      <RefreshCw className={cn("h-4 w-4 text-slate-300 transition-transform", refreshing && "animate-spin")} />
                      <div>
                        <p className="text-[10px] text-slate-400 font-medium">Last update</p>
                        <p className="font-bold text-slate-300 text-[11px]">
                          {balance ? new Date(balance.at).toLocaleDateString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "27 Oct 10:46 AM"}
                        </p>
                      </div>
                    </button>
                  </div>

                  {balanceError && <p className="text-xs text-amber-200">{balanceError}</p>}

                  {/* Add Cash & Cash Out buttons row */}
                  <div className="grid grid-cols-2 gap-3 pt-1">
                    <button
                      onClick={() => setStep("cash")}
                      className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#38bdf8] hover:bg-[#0ea5e9] text-slate-950 font-black text-xs sm:text-sm shadow-sm transition hover:scale-[1.02] active:scale-95">
                      <span className="grid h-5 w-5 place-items-center rounded-full bg-slate-950/15 text-slate-950 text-[10px] font-black">
                        $
                      </span>
                      Add Cash
                    </button>

                    <button
                      onClick={() => setStep("redeem")}
                      className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-white/10 bg-[#182035] hover:bg-[#1f2942] text-white font-bold text-xs sm:text-sm transition hover:scale-[1.02] active:scale-95">
                      <span className="grid h-5 w-5 place-items-center rounded-full bg-white/10 text-white text-[10px] font-bold">
                        $
                      </span>
                      Cash Out
                    </button>
                  </div>

                  {/* Login details, always visible: username + password (eye to show, copy) */}
                  {credError && <p role="alert" className="rounded-xl bg-rose-500/15 p-3 text-xs text-rose-200">{credError}</p>}
                  <div className="flex items-center justify-between rounded-xl border border-white/10 bg-[#182035] px-4 py-3.5">
                    <span className="font-mono text-sm font-bold text-slate-200" data-testid="field-username">{creds?.username ?? access?.account?.username}</span>
                    <button type="button" aria-label="Copy username" onClick={() => access?.account && copyUsername(creds?.username ?? access.account.username)}
                      className="p-1 text-slate-400 transition hover:text-white">
                      {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                    </button>
                  </div>
                  <div className="flex items-center justify-between rounded-xl border border-white/10 bg-[#182035] px-4 py-3.5">
                    <span className="font-mono text-sm font-bold text-slate-200" data-testid="field-password">{!creds ? "••••••" : showPass ? creds.password : "••••••"}</span>
                    <span className="flex items-center gap-2 text-slate-400">
                      <button type="button" onClick={() => setShowPass((v) => !v)} aria-label={showPass ? "Hide password" : "Show password"} className="p-1 transition hover:text-white">
                        {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                      <button type="button" aria-label="Copy password" onClick={copyPassword} className="p-1 transition hover:text-white">
                        {copiedPass ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                      </button>
                    </span>
                  </div>

                  {note && (
                    <p role={note.tone === "error" ? "alert" : "status"} className={"rounded-xl p-3 text-xs " + (note.tone === "error" ? "bg-rose-500/15 text-rose-200" : "bg-emerald-500/15 text-emerald-100")}>{note.text}</p>
                  )}
                  {confirming ? (
                    <div className="rounded-xl border border-white/15 bg-black/20 p-3" data-testid="confirm-box">
                      <p className="text-xs text-slate-200">{confirming === "reset" ? "Set a new password for this login? The old one stops working." : "Remove this login from your list? The game balance must be $0.00. You can get a new login later."}</p>
                      <div className="mt-3 grid grid-cols-2 gap-2">
                        <button disabled={working} data-testid="confirm-yes" onClick={confirming === "reset" ? resetPassword : removeLogin}
                          className={"inline-flex h-10 items-center justify-center gap-2 rounded-xl text-xs font-black transition disabled:opacity-50 " + (confirming === "reset" ? "bg-[#38bdf8] text-slate-950 hover:bg-[#0ea5e9]" : "bg-rose-500 text-white hover:bg-rose-400")}>
                          {working && <Spinner className="h-3.5 w-3.5" />}{confirming === "reset" ? "Reset" : "Remove"}
                        </button>
                        <button disabled={working} onClick={() => setConfirming(null)} className="h-10 rounded-xl border border-white/20 text-xs font-bold text-white hover:bg-white/10">Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <button onClick={() => { setNote(null); setConfirming("reset"); }} className="h-12 flex-1 rounded-xl border border-white/15 bg-transparent text-sm font-semibold text-slate-200 transition hover:bg-white/5">Reset password</button>
                      <button onClick={() => { setNote(null); setConfirming("remove"); }} aria-label="Remove login" data-testid="remove-login"
                        className="grid h-12 w-14 place-items-center rounded-xl bg-rose-500/20 text-rose-400 transition hover:bg-rose-500/30"><Trash2 className="h-5 w-5" /></button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* RIGHT COLUMN: Free Spin Card + Promo Banner + Transactions Area */}
            <div className="flex flex-col gap-5">
              
              {/* Tired of losing? Try Free Spin card */}
              <TiredOfLosingCard />

              {/* Test your luck promo banner: Loss Streak Diamond Shield */}
              <TestYourLuckBanner />

              {/* Transactions Container */}
              <div className="min-h-[360px] rounded-3xl border border-white/10 bg-[#121829] p-8 flex flex-col items-center justify-center text-center shadow-xl">
                <div className="grid h-16 w-16 place-items-center rounded-3xl bg-white/5 border border-white/10 text-slate-400 mb-3">
                  <FileText className="h-8 w-8 stroke-[1.5]" />
                </div>
                <p className="text-base font-bold text-slate-300">
                  Your transactions will be displayed here
                </p>
                <p className="text-xs text-slate-400 mt-1 max-w-sm">
                  Recent deposits, redeems, and play sessions appear here automatically.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Step: Add Cash */}
        {step === "cash" && access && (
          <div className="max-w-xl mx-auto rounded-3xl border border-white/10 bg-[#121829] p-6 sm:p-8 shadow-2xl">
            <FullscreenCash state={access} onBack={() => setStep("dashboard")} onDone={() => { loadAccess(); refreshBalance(); }} />
          </div>
        )}

        {/* Step: Redeem / Cash Out */}
        {step === "redeem" && access && (
          <div className="max-w-xl mx-auto rounded-3xl border border-white/10 bg-[#121829] p-6 sm:p-8 shadow-2xl">
            <FullscreenRedeem state={access} onBack={() => setStep("dashboard")} onDone={() => { loadAccess(); refreshBalance(); }} />
          </div>
        )}
      </div>

      {showLimits && (
        <CashoutLimitsModal onDone={() => { setShowLimits(false); setShowCredsModal(true); }} />
      )}

      {/* Login Details Modal Dialog (Screenshot 4) */}
      {showCredsModal && (
        <FullscreenLoginDetailsModal
          slug={slug}
          game={currentGame}
          onCash={() => { setShowCredsModal(false); setStep("cash"); }}
          onClose={() => setShowCredsModal(false)}
        />
      )}
    </div>
  );
}

/** Login Details Modal popup matching Screenshot 4 */
function FullscreenLoginDetailsModal({
  slug, game, onCash, onClose
}: {
  slug: string; game: { name: string; image_url: string | null }; onCash: () => void; onClose: () => void;
}) {
  const [creds, setCreds] = useState<{ username: string; password: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showPass, setShowPass] = useState(false);
  const [copiedUser, setCopiedUser] = useState(false);
  const [copiedPass, setCopiedPass] = useState(false);

  useEffect(() => {
    api<{ username: string; password: string }>(`/games/${slug}/access/credentials`)
      .then((c) => { setCreds(c); setError(null); })
      .catch((e) => setError(errorMessage(e)));
  }, [slug]);

  const copy = async (txt: string, isUser: boolean) => {
    try {
      await navigator.clipboard.writeText(txt);
      if (isUser) { setCopiedUser(true); setTimeout(() => setCopiedUser(false), 2000); }
      else { setCopiedPass(true); setTimeout(() => setCopiedPass(false), 2000); }
    } catch { /* clipboard */ }
  };

  const coverUrl = getGameCover(game);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/80 p-4 backdrop-blur-md animate-in fade-in duration-200"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      
      <div className="w-full max-w-sm rounded-3xl border border-white/15 bg-[#131927] p-6 text-white shadow-2xl relative animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-xl font-black text-white tracking-tight">Login details</h3>
            <p className="text-xs text-slate-400 font-semibold mt-0.5">Your login is ready to play!</p>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded-xl p-1 text-slate-400 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Game icon & title chip */}
        <div className="mt-4 flex items-center gap-3 rounded-2xl bg-white/5 border border-white/10 p-3">
          <div className="h-10 w-10 shrink-0 overflow-hidden rounded-xl border border-white/10 bg-slate-900">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={coverUrl} alt={game.name} className="h-full w-full object-cover" />
          </div>
          <p className="text-base font-extrabold text-white truncate">{game.name}</p>
        </div>

        {/* Section Divider */}
        <div className="my-4 flex items-center gap-2">
          <div className="h-px flex-1 bg-white/10" />
          <span className="text-[10px] font-extrabold uppercase tracking-widest text-slate-400">LOGIN DETAILS</span>
          <div className="h-px flex-1 bg-white/10" />
        </div>

        {error && <p className="mb-3 rounded-xl bg-rose-500/15 p-3 text-xs text-rose-200">{error}</p>}

        {!creds && !error ? (
          <div className="grid h-28 place-items-center"><Spinner className="h-6 w-6 text-sky-400" /></div>
        ) : creds && (
          <div className="space-y-3">
            {/* Username field */}
            <div className="flex items-center justify-between rounded-xl border border-white/10 bg-[#182035] px-4 py-3">
              <span className="font-mono text-sm font-bold text-white truncate">
                {creds.username}
              </span>
              <button
                type="button"
                onClick={() => copy(creds.username, true)}
                className="text-slate-400 hover:text-white transition p-1">
                {copiedUser ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>

            {/* Password field */}
            <div className="flex items-center justify-between rounded-xl border border-white/10 bg-[#182035] px-4 py-3">
              <span className="font-mono text-sm font-bold text-white truncate">
                {showPass ? creds.password : "••••••"}
              </span>
              <div className="flex items-center gap-2 text-slate-400">
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  className="hover:text-white transition p-1"
                  aria-label={showPass ? "Hide password" : "Show password"}>
                  {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
                <button
                  type="button"
                  onClick={() => copy(creds.password, false)}
                  className="hover:text-white transition p-1"
                  aria-label="Copy password">
                  {copiedPass ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Action buttons */}
        <div className="mt-5 grid grid-cols-2 gap-3">
          <button
            onClick={onCash}
            className="inline-flex h-11 items-center justify-center rounded-xl bg-[#38bdf8] hover:bg-[#0ea5e9] text-slate-950 font-black text-sm transition active:scale-95">
            Add Cash
          </button>
          <button
            onClick={onClose}
            className="inline-flex h-11 items-center justify-center rounded-xl border border-white/10 bg-[#182035] hover:bg-[#1f2942] text-white font-bold text-sm transition">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

/** Add Cash Screen embedded cleanly in the page */
function FullscreenCash({ state, onBack, onDone }: { state: Access; onBack: () => void; onDone: () => void }) {
  const { min, max, quick } = state.cash;
  const wallet = num(state.wallet_balance), bonus = num(state.bonus_balance);
  const bonusUsable = !!state.bonus_enabled && bonus > 0;
  const lowWallet = !!state.wallet_funded && wallet < 1 && bonusUsable;
  const [source, setSource] = useState<"wallet" | "bonus">(lowWallet ? "bonus" : "wallet");
  const [amount, setAmount] = useState(lowWallet ? Math.min(10, bonus) : (quick[1] ?? 10));
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<CashResult | null>(null);
  const attempt = useRef<{ k: string; key: string } | null>(null);

  const cap = source === "bonus" ? Math.min(Number(max), bonus) : Number(max);
  const clamp = (n: number) => Math.max(0, Math.min(cap, Math.round(n * 100) / 100));
  const valid = source === "bonus" ? amount > 0 && amount <= cap && (amount >= 1 || amount === bonus) : amount >= Number(min) && amount <= Number(max);

  const submit = async () => {
    setBusy(true); setError(null); setDone(null);
    const k = `${source}:${amount}`;
    if (!attempt.current || attempt.current.k !== k) attempt.current = { k, key: crypto.randomUUID() };
    try {
      const r = await api<CashResult>(`/games/${state.game.slug}/cash`, { method: "POST", body: { amount: amount.toFixed(2), source, idempotency_key: attempt.current.key } });
      setDone(r); attempt.current = null; onDone(); notifyWalletChanged();
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  };

  return (
    <div>
      <div className="flex items-center justify-between pb-4 border-b border-white/10">
        <h2 className="text-xl font-black text-white">Add Cash to {state.game.name}</h2>
        <button onClick={onBack} className="text-xs font-bold text-sky-400 hover:underline">← Back to Game</button>
      </div>

      {(state.wallet_funded || bonusUsable) && (
        <div role="group" aria-label="Pay with" className="mt-5 grid grid-cols-2 gap-1 rounded-2xl bg-white/5 border border-white/10 p-1">
          {([["wallet", "Wallet", state.wallet_funded ? money2(wallet) : null], ["bonus", "Bonus", money2(bonus)]] as const).map(([key, label, bal]) => (
            <button key={key} onClick={() => setSource(key)} aria-pressed={source === key} disabled={key === "bonus" && !bonusUsable}
              className={cn("rounded-xl px-3 py-2 text-xs sm:text-sm font-bold transition disabled:opacity-40", source === key ? (key === "bonus" ? "bg-[#ffd966] text-slate-950 font-black" : "bg-sky-400 text-slate-950 font-black") : "text-slate-300 hover:bg-white/10")}>
              {label}{bal && <span className="ml-1.5 font-extrabold">{bal}</span>}
            </button>
          ))}
        </div>
      )}

      <p className="mt-5 text-center text-xs font-semibold text-slate-400">Amount{source === "bonus" ? " from bonus balance" : ""}</p>
      <div className="mt-2 flex items-center justify-between rounded-2xl bg-white/5 border border-white/10 px-5 py-4">
        <button onClick={() => setEditing((v) => !v)} aria-label="Edit amount" className="text-sky-400"><Pencil className="h-4 w-4" /></button>
        {editing ? (
          <input autoFocus inputMode="decimal" aria-label="Amount in dollars" value={amount}
            onChange={(e) => setAmount(clamp(Number(e.target.value.replace(/[^0-9.]/g, "")) || 0))}
            onBlur={() => setEditing(false)} className="w-32 bg-transparent text-center text-4xl font-black text-white outline-none" />
        ) : <p className="text-4xl font-black text-white tabular-nums">{money(amount)}</p>}
        <button onClick={() => setAmount(0)} aria-label="Clear amount" className="text-slate-400 hover:text-white"><X className="h-5 w-5" /></button>
      </div>

      <div className="mt-3 grid grid-cols-5 gap-1.5">
        {quick.map((q) => <button key={q} onClick={() => setAmount((a) => clamp(a + q))} className="rounded-xl bg-white/5 border border-white/10 py-3 text-xs font-black text-sky-400 hover:bg-white/10">+{q}</button>)}
        <button onClick={() => setAmount((a) => clamp(a * 2))} className="rounded-xl bg-white/5 border border-white/10 py-3 text-xs font-black text-sky-400 hover:bg-white/10">X2</button>
        <button onClick={() => setAmount(0)} aria-label="Reset amount" className="grid place-items-center rounded-xl bg-rose-500/15 border border-rose-500/20 text-rose-300 hover:bg-rose-500/25"><Trash2 className="h-4 w-4" /></button>
      </div>

      <dl className="mt-5 space-y-2 rounded-2xl bg-white/5 border border-white/10 p-4 text-xs text-slate-300">
        {state.wallet_funded && <div className="flex justify-between"><dt className="text-slate-400">Wallet balance</dt><dd className="font-bold text-white">{state.wallet_balance !== null && state.wallet_balance !== undefined ? money2(state.wallet_balance) : "—"}</dd></div>}
        {state.bonus_enabled && <div className="flex justify-between"><dt className="text-slate-400">Bonus balance</dt><dd className="font-bold text-[#ffd966]">{money2(bonus)}</dd></div>}
        <div className="flex justify-between"><dt className="text-slate-400">{source === "bonus" ? "From bonus" : "Add cash range"}</dt><dd className="font-bold text-white">{source === "bonus" ? `min ${money(state.bonus_min ?? "1")} or the whole balance` : `${money(min)} – ${money(max)}`}</dd></div>
      </dl>

      {error && <p role="alert" className="mt-3 rounded-2xl bg-rose-500/15 border border-rose-500/20 p-3 text-xs text-rose-200">{error}</p>}
      {done && (() => {
        const from = done.source === "bonus" ? "bonus balance" : "wallet";
        const ok = done.status === "completed";
        const held = done.status === "needs_review";
        const failed = done.status === "failed";
        const text = ok ? `${money2(done.amount)} added to the game${done.source === "bonus" ? " from your bonus balance" : ""}.`
          : failed ? `The game could not add the cash, so nothing was charged: your ${from} is unchanged.${done.reason ? ` Provider said: ${done.reason}` : done.note ? ` (${done.note})` : ""}`
          : held ? `Your funds are held while we confirm the credit with the game. Nothing is lost.`
          : `Request for ${money(done.amount)} received. It will be credited once our team confirms your payment.`;
        return (
          <p role={failed ? "alert" : "status"} data-testid="cash-result" data-status={done.status}
            className={cn("mt-3 rounded-2xl border p-3 text-xs", ok ? "bg-emerald-500/15 border-emerald-500/20 text-emerald-200" : failed ? "bg-rose-500/15 border-rose-500/25 text-rose-200" : "bg-amber-300/10 border-amber-300/25 text-amber-100")}>
            {text}
          </p>
        );
      })()}

      <div className="mt-6 flex gap-3">
        <button className="flex-1 h-12 rounded-2xl bg-[#38bdf8] hover:bg-[#0ea5e9] text-slate-950 font-black text-sm transition active:scale-95 shadow-md disabled:opacity-50"
          onClick={submit} disabled={busy || !valid}>
          {busy ? <Spinner /> : null} Confirm Add Cash
        </button>
        <button className="h-12 px-6 rounded-2xl border border-white/10 bg-[#182035] hover:bg-[#1f2942] text-white font-bold text-sm transition"
          onClick={onBack}>
          Back
        </button>
      </div>
    </div>
  );
}

/** Cash Out / Redeem Screen embedded cleanly in the page */
function FullscreenRedeem({ state, onBack, onDone }: { state: Access; onBack: () => void; onDone: () => void }) {
  const [p, setP] = useState<RedeemPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [showRules, setShowRules] = useState(false);
  const [result, setResult] = useState<RedeemResult | null>(null);
  const key = useRef<string | null>(null);

  const load = useCallback(async () => {
    setRefreshing(true);
    try { setP(await api<RedeemPreview>(`/games/${state.game.slug}/redeem`)); setError(null); } catch (e) { setError(errorMessage(e)); } finally { setRefreshing(false); }
  }, [state.game.slug]);
  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    setBusy(true); setError(null); setResult(null);
    key.current = key.current ?? crypto.randomUUID();
    try {
      const r = await api<RedeemResult>(`/games/${state.game.slug}/redeem`, { method: "POST", body: { idempotency_key: key.current, confirm_void: confirm } });
      setResult(r); key.current = null; setConfirm(false); await load(); onDone(); notifyWalletChanged();
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  };

  const bal = p?.game_balance != null ? Number(p.game_balance) : null;
  const bonusMode = p?.mode === "bonus";
  const bonusMin = Number(p?.bonus_rule?.min ?? 60);
  const belowMin = !!p && !p.can_redeem && bal !== null && (bonusMode ? bal < bonusMin : !!p.rule && bal < Number(p.rule.min));
  const added = p?.added;

  return (
    <div data-testid="cashout-screen">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-black text-white">Cash Out</h2>
        <button onClick={onBack} aria-label="Close" className="grid h-9 w-9 place-items-center rounded-full text-slate-400 transition hover:bg-white/10 hover:text-white"><X className="h-5 w-5" /></button>
      </div>

      {/* game + login + live balance */}
      <div className="mt-4 flex items-center gap-4 rounded-2xl border border-white/10 bg-black/30 p-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={getGameCover(state.game)} alt="" className="h-16 w-16 shrink-0 rounded-xl border border-white/10 object-cover" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-lg font-extrabold text-white">{state.game.name}</p>
          <p className="mt-0.5 text-xs text-slate-400">Login</p>
          <p className="truncate font-mono text-sm text-slate-200">{state.account?.username}</p>
        </div>
        <div className="shrink-0 text-right">
          <button onClick={load} aria-label="Refresh balance" className="text-slate-400 transition hover:text-white"><RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} /></button>
          <p className="mt-1 text-xs text-slate-400">Balance</p>
          <p className="text-xl font-black text-white" data-testid="redeem-balance">{bal !== null ? money2(bal) : "—"}</p>
        </div>
      </div>

      {!p && !error && <div className="grid h-32 place-items-center"><Spinner className="h-6 w-6 text-sky-400" /></div>}

      {p && (
        <>
          {/* what funded this play */}
          <div className="mt-4 space-y-3.5 rounded-2xl border border-white/10 bg-black/30 p-5 text-[15px]">
            <div className="flex items-center justify-between"><span className="text-slate-400">Session</span><span className="font-bold text-white" data-testid="redeem-session">{added?.session ?? "Cash"}</span></div>
            <div className="flex items-center justify-between"><span className="text-slate-400">Cash added to game</span><span className="font-bold text-sky-400" data-testid="redeem-cash-added">{money2(added?.cash ?? 0)}</span></div>
            <div className="flex items-center justify-between"><span className="text-slate-400">Bonus added to game</span><span className="font-bold text-[#ffd966]" data-testid="redeem-bonus-added">{money2(added?.bonus ?? 0)}</span></div>
            <div className="flex items-center justify-between"><span className="text-slate-400">Game balance (full)</span><span className="font-bold text-white">{bal !== null ? money2(bal) : "—"}</span></div>
            {p.needs_confirm && <div className="flex items-center justify-between"><span className="text-slate-400">{bonusMode ? "Not carried over" : "Voided (above maximum)"}</span><span className="font-bold text-rose-400" data-testid="redeem-voided">{money2(p.voided ?? 0)}</span></div>}
          </div>

          {/* cashout range, with the detailed rules behind the (i) */}
          <div className="mt-3 flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-black/30 px-5 py-4 text-sm" data-testid="redeem-rule">
            {bonusMode ? (
              <span className="text-slate-400" data-testid="bonus-range">
                Bonus cashout from <b className="text-white">{money(bonusMin)}</b>:{" "}
                {p.bonus_rule?.table.map((t, i) => <span key={t.made}>{i > 0 && " · "}<b className="text-white">{t.made}</b> pays <b className="text-emerald-400">{t.wallet}</b></span>)}{" "}to your wallet
              </span>
            ) : (
              <span className="text-slate-400">
                Cashouts range{" "}
                {p.rule ? <b className="text-white">from {money(p.rule.min)} to {money(p.rule.max)}</b> : <b className="text-white">unlocks when you add $5 or more of your own cash</b>}
              </span>
            )}
            <button onClick={() => setShowRules(true)} aria-label="Cashout rules in detail" data-testid="redeem-info"
              className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-white/15 bg-white/5 text-xs font-black italic text-slate-300 transition hover:bg-white/10 hover:text-white">i</button>
          </div>

          {p.needs_confirm && (
            <label className="mt-3 flex cursor-pointer items-start gap-2.5 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-sm text-rose-200">
              <input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} data-testid="redeem-confirm" className="mt-0.5 h-4 w-4 accent-rose-400" />
              <span>{bonusMode
                ? <>I understand only {money2(p.payout ?? 0)} will be added to my wallet and the other {money2(p.voided ?? 0)} of my bonus winnings will not be carried over.</>
                : <>I understand {money2(p.voided ?? 0)} above my maximum will be voided and cannot be recovered.</>}</span>
            </label>
          )}

          {!p.can_redeem && p.reason && (
            <div role="alert" className="mt-3 flex items-start gap-3 rounded-2xl border border-rose-500/30 bg-rose-950/40 p-4 text-sm text-rose-200" data-testid="redeem-reason">
              <Info className="mt-0.5 h-5 w-5 shrink-0 text-rose-400" />
              <div>
                <p className="font-bold text-rose-400">{belowMin ? "Below Minimum Cashout!" : "Can't cash out yet"}</p>
                <p className="mt-0.5">{belowMin ? `You must have at least ${money2(bonusMode ? bonusMin : Number(p.rule!.min))} in the game to cash out.` : p.reason}</p>
              </div>
            </div>
          )}
        </>
      )}

      {error && <p role="alert" className="mt-3 rounded-2xl bg-rose-500/15 p-3 text-sm text-rose-200">{error}</p>}
      {result && (
        <p role="status" data-testid="redeem-result" className={cn("mt-3 rounded-2xl p-3 text-sm", result.status === "completed" ? "bg-emerald-500/15 text-emerald-200" : "bg-amber-300/10 text-amber-100")}>
          {result.status === "completed" ? `${money2(result.payout)} was added to your wallet${Number(result.voided) > 0 ? ` (${money2(result.voided)} above your maximum was voided)` : ""}.` : result.note ?? "Could not complete the cash out."}
        </p>
      )}

      <div className="mt-5 grid grid-cols-2 gap-3">
        <button className="h-14 rounded-2xl bg-[#38bdf8] text-base font-black text-slate-950 shadow-md transition hover:bg-[#0ea5e9] active:scale-95 disabled:cursor-not-allowed disabled:opacity-45"
          data-testid="redeem-submit" onClick={submit} disabled={busy || !p?.can_redeem || (p.needs_confirm && !confirm)}>
          {busy ? <Spinner /> : "Cash Out"}
        </button>
        <button className="h-14 rounded-2xl border border-white/10 bg-black/40 text-base font-bold text-white transition hover:bg-white/10" onClick={onBack}>Close</button>
      </div>

      {showRules && p && <CashoutRulesDetail table={p.table} note={p.note} rule={p.rule} bonus={p.bonus_rule} onClose={() => setShowRules(false)} />}
    </div>
  );
}

/** The (i) popup: how cashout works, the full limits table (the player's row highlighted), and what bonus money does. */
function CashoutRulesDetail({ table, note, rule, bonus, onClose }: { table: RedeemPreview["table"]; note: string; rule: RedeemPreview["rule"]; bonus?: RedeemPreview["bonus_rule"]; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-[60] grid place-items-center overflow-y-auto bg-black/80 p-4 backdrop-blur-md" role="dialog" aria-modal="true" aria-label="Cashout rules" data-testid="rules-detail"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="relative my-auto w-full max-w-md rounded-3xl border border-white/10 bg-[#0B0F1A] p-5 text-white shadow-2xl sm:p-6">
        <button onClick={onClose} aria-label="Close" className="absolute right-4 top-4 grid h-9 w-9 place-items-center rounded-full border border-white/10 bg-white/5 text-slate-400 transition hover:text-white"><X className="h-4 w-4" /></button>
        <h3 className="pr-10 text-xl font-black">How cashout works</h3>
        <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-slate-300" data-testid="how-cashout">
          <li>Add cash to this game (from your wallet or your bonus balance) and play.</li>
          <li>The <b>latest cash you added to this game</b> sets your cashout range: a minimum and a maximum (table below). Bonus added to the game does not count towards the range, and adding under $5 does not unlock cashing out.</li>
          <li>Press Cash Out. Your whole game balance leaves the game and the allowed amount is added to your <b>wallet</b>. Anything above the maximum is voided, and you confirm that first.</li>
          <li>One cash out per cash added. To cash out again, add cash to the game again.</li>
          <li>From your wallet you can then withdraw to your payment method (minimum $50).</li>
        </ol>
        <div className="mt-4 overflow-hidden rounded-2xl border border-white/10">
          <table className="w-full text-left text-sm">
            <thead className="bg-[#121826] text-[11px] font-extrabold uppercase tracking-wider text-blue-400"><tr><th className="px-4 py-2.5">Cash added</th><th className="px-3 py-2.5">Minimum</th><th className="px-3 py-2.5">Maximum</th></tr></thead>
            <tbody>
              {table.map((row, i) => (
                <tr key={row.deposit} className={cn("border-t border-white/[0.06]", rule?.row === i && "bg-sky-500/15")}>
                  <td className="px-4 py-2.5 font-bold">{row.deposit}</td><td className="px-3 py-2.5 text-slate-300">{row.min}</td><td className="px-3 py-2.5 text-slate-300">{row.max}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-slate-400">x3 / x12 mean 3 / 12 times the cash you added. {note}</p>
        <div className="mt-4 rounded-2xl border border-[#ffd966]/30 bg-[#ffd966]/10 p-4 text-sm text-[#ffd966]" data-testid="bonus-rule-detail">
          <p className="font-bold">Bonus balance rule</p>
          <p className="mt-1 text-[#ffd966]/90">Bonus can only be added to a game, never withdrawn directly. If a game was funded <b>only by bonus</b> (no cash of your own added), the game balance must reach <b>{bonus?.min ? `$${Number(bonus.min).toFixed(0)}` : "$60"}</b> to cash out, and your wallet is credited a fixed amount:</p>
          <table className="mt-2 w-full text-left">
            <thead className="text-[11px] font-extrabold uppercase tracking-wider text-[#ffd966]/70"><tr><th className="py-1">Game balance</th><th className="py-1">Credited to wallet</th></tr></thead>
            <tbody>{(bonus?.table ?? []).map((t) => <tr key={t.made} className="border-t border-[#ffd966]/20"><td className="py-1.5 font-bold">{t.made}</td><td className="py-1.5 font-bold text-emerald-300">{t.wallet}</td></tr>)}</tbody>
          </table>
          <p className="mt-2 text-xs text-[#ffd966]/80">{bonus?.note ?? "The rest of the balance is not carried over."} If you add your own cash to the game, the cash table above applies instead.</p>
        </div>
        <button onClick={onClose} className="mt-4 h-12 w-full rounded-2xl bg-gradient-to-r from-[#3B82F6] to-[#8B5CF6] text-base font-black text-white transition hover:brightness-110 active:scale-[0.98]">Got it</button>
      </div>
    </div>
  );
}
