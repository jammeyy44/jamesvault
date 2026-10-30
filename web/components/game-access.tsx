"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Copy, Download, Eye, EyeOff, FileText, FlaskConical, Gift, Info, KeyRound, Pencil, Play, RefreshCw, Sparkles, Trash2, X } from "lucide-react";
import { Spinner } from "./ui/bits";
import { api, ApiError, errorMessage, type Game } from "@/lib/api";
import { OPEN_WALLET_EVENT, notifyWalletChanged } from "./wallet-panel";
import { TestYourLuckBanner } from "./test-your-luck";
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
type CashResult = { status: string; sandbox: boolean; amount: string; note: string | null; source?: "wallet" | "bonus" };

const num = (v?: string | null) => Number(v ?? 0);
const canAddCash = (a: Access) => a.cash_enabled || (!!a.bonus_enabled && num(a.bonus_balance) > 0);
const money = (v: string | number) => `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: Number.isInteger(Number(v)) ? 0 : 2, maximumFractionDigits: 2 })}`;
const money2 = (v: string | number) => `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const DEFAULT_COVERS: Record<string, string> = {
  "royal-vault": "/images/game_royal_vault.jpg",
  "estar": "/images/game_estar.jpg",
  "royal-treasure": "/images/game_royal_treasure.jpg",
  "yolo-lucky-wheel": "/images/game_yolo_wheel.jpg",
  "vblink": "/images/game_vblink.jpg",
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

const btnSky = "inline-flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-[#38bdf8] hover:bg-[#0ea5e9] text-slate-950 font-black text-sm transition hover:scale-[1.02] active:scale-95 disabled:opacity-50 shadow-md";
const btnDark = "inline-flex h-12 w-full items-center justify-center gap-2 rounded-2xl border border-white/10 bg-[#182035] hover:bg-[#1f2942] text-white font-bold text-sm transition hover:scale-[1.02] active:scale-95";

export function GameAccessModal({ game, onClose }: { game: Game; onClose: () => void }) {
  const [step, setStep] = useState<"home" | "cash" | "redeem">("home");
  const [state, setState] = useState<Access | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [fresh, setFresh] = useState(false);
  const [showCredsModal, setShowCredsModal] = useState(false);
  const panel = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try { setState(await api<Access>(`/games/${game.slug}/access`)); } catch (e) { setError(errorMessage(e)); }
  }, [game.slug]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.focus();
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = prev; };
  }, [onClose]);

  const getAccess = async () => {
    setBusy(true); setError(null);
    try {
      const res = await api<Access>(`/games/${game.slug}/access`, { method: "POST" });
      setState(res);
      setFresh(true);
      setStep("home");
      setShowCredsModal(true); // Open the Screenshot 4 "Login details" modal immediately!
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/85 p-3 sm:p-5 backdrop-blur-md overflow-y-auto"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      
      <div ref={panel} tabIndex={-1} role="dialog" aria-modal="true" aria-label={`${game.name} access`}
        className={cn(
          "relative my-auto w-full overflow-hidden rounded-3xl border border-white/10 bg-[#0c101c] text-white shadow-2xl outline-none transition-all",
          step === "home" ? "max-w-4xl" : "max-w-lg"
        )}>

        {/* Top bar with close button */}
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-3.5 bg-[#101626]/80">
          <div className="flex items-center gap-2">
            <span className="grid h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-extrabold uppercase tracking-wider text-slate-300">{game.name}</span>
          </div>
          <button onClick={onClose} aria-label="Close"
            className="grid h-8 w-8 place-items-center rounded-xl border border-white/10 bg-white/5 text-slate-300 hover:text-white hover:bg-white/10 transition">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4 sm:p-6">
          {!state && !error && (
            <div className="grid h-64 place-items-center">
              <div className="flex flex-col items-center gap-3">
                <Spinner className="h-8 w-8 text-sky-400" />
                <p className="text-sm font-bold text-slate-400">Loading game session…</p>
              </div>
            </div>
          )}

          {error && !state && (
            <div className="space-y-4 p-4 text-center">
              <p role="alert" className="rounded-2xl bg-rose-500/15 border border-rose-500/20 p-4 text-sm text-rose-200">{error}</p>
              <button className={btnDark} onClick={onClose}>Close</button>
            </div>
          )}

          {state && step === "home" && (
            <GameDashboard
              state={state}
              busy={busy}
              error={error}
              fresh={fresh}
              onGetAccess={getAccess}
              onCash={() => setStep("cash")}
              onRedeem={() => setStep("redeem")}
              onOpenCreds={() => setShowCredsModal(true)}
              onRemoved={() => { setFresh(false); load(); }}
              onClose={onClose}
            />
          )}

          {state && step === "cash" && (
            <Cash state={state} onClose={onClose} onBack={() => setStep("home")} onRedeem={() => setStep("redeem")} onChanged={load} />
          )}

          {state && step === "redeem" && (
            <Redeem state={state} onClose={onClose} onBack={() => setStep("home")} onChanged={load} />
          )}
        </div>
      </div>

      {/* Login details modal popup (Matches Screenshot 4) */}
      {state && showCredsModal && (
        <LoginDetailsModal
          slug={state.game.slug}
          game={state.game}
          onCash={() => { setShowCredsModal(false); setStep("cash"); }}
          onClose={() => setShowCredsModal(false)}
        />
      )}
    </div>
  );
}

/** 2-Column Game Dashboard matching Screenshots 1, 2, and 3 */
function GameDashboard({
  state, busy, error, onGetAccess, onCash, onRedeem, onOpenCreds, onRemoved
}: {
  state: Access; busy: boolean; error: string | null; fresh: boolean;
  onGetAccess: () => void; onCash: () => void; onRedeem: () => void;
  onOpenCreds: () => void; onRemoved: () => void; onClose: () => void;
}) {
  const slug = state.game.slug;
  const [balance, setBalance] = useState<{ amount: string; at: string } | null>(null);
  const [balanceError, setBalanceError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [confirming, setConfirming] = useState<"reset" | "remove" | null>(null);
  const [working, setWorking] = useState(false);
  const [note, setNote] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const resetPassword = async () => {
    setWorking(true); setNote(null);
    try {
      await api(`/games/${slug}/access/reset-password`, { method: "POST" });
      setConfirming(null);
      setNote({ tone: "ok", text: "Your password was changed. Open “View login details” to see the new one." });
    } catch (e) { setNote({ tone: "error", text: errorMessage(e) }); } finally { setWorking(false); }
  };
  const removeLogin = async () => {
    setWorking(true); setNote(null);
    try { await api(`/games/${slug}/access`, { method: "DELETE" }); onRemoved(); }
    catch (e) { setConfirming(null); setNote({ tone: "error", text: errorMessage(e) }); } finally { setWorking(false); }
  };

  const refresh = useCallback(async () => {
    if (!state.account) return;
    setRefreshing(true); setBalanceError(null);
    try {
      const r = await api<{ balance: string; as_of: string }>(`/games/${slug}/balance`);
      setBalance({ amount: r.balance, at: r.as_of });
    } catch (e) {
      setBalance(null);
      setBalanceError(errorMessage(e));
    } finally {
      setRefreshing(false);
    }
  }, [slug, state.account]);

  useEffect(() => { refresh(); }, [refresh]);

  const copyUsername = async (u: string) => {
    try {
      await navigator.clipboard.writeText(u);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard */ }
  };

  const coverUrl = getGameCover(state.game);
  const hasAccount = !!state.account;

  return (
    <div className="grid grid-cols-1 md:grid-cols-[360px_1fr] gap-6 items-start">
      {/* LEFT COLUMN: The Game Profile Card (Screenshots 1, 2, 3) */}
      <div className="rounded-3xl border border-white/10 bg-[#121829] p-5 sm:p-6 shadow-2xl flex flex-col">
        {/* Game artwork poster */}
        <div className="relative aspect-[4/3] w-full overflow-hidden rounded-2xl bg-slate-900 border border-white/10 shadow-md">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={coverUrl} alt={state.game.name} className="h-full w-full object-cover" />
        </div>

        {/* Title row with Mint Green circular play button */}
        <div className="mt-4 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-xl sm:text-2xl font-black text-white tracking-tight truncate" data-testid="panel-title">
              {state.game.name}
            </h2>
            <p className="text-xs text-slate-400 font-semibold truncate mt-0.5">
              {state.game.category || "Slots, Table Games"}
            </p>
          </div>
          
          <button
            onClick={hasAccount ? onOpenCreds : onGetAccess}
            aria-label="Play game"
            className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-emerald-400 hover:bg-emerald-300 text-slate-950 font-black shadow-[0_4px_20px_rgba(52,211,153,0.5)] transition hover:scale-105 active:scale-95">
            <Play className="h-5 w-5 fill-current ml-0.5" />
          </button>
        </div>

        <hr className="my-4 border-white/10" />

        {/* State A: User does NOT have an account yet (Screenshot 3) */}
        {!hasAccount && (
          <div className="space-y-4">
            {/* Info notice box */}
            <div className="flex items-center gap-3 rounded-2xl border border-sky-400/25 bg-sky-500/15 p-3.5 text-xs sm:text-sm text-sky-200">
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

            {/* Sky blue Get Access button with loading dots state */}
            <button
              onClick={onGetAccess}
              disabled={busy}
              className={btnSky}>
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

        {/* State B: User HAS an account (Screenshots 1 & 2) */}
        {hasAccount && (
          <div className="space-y-4">
            {/* Balance + Refresh section */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-2xl sm:text-3xl font-black text-white tabular-nums" data-testid="home-balance">
                  {balance ? money2(balance.amount) : "$0.00"}
                </p>
                <p className="text-xs text-slate-400 font-semibold">Balance</p>
              </div>

              <button
                onClick={refresh}
                aria-label="Refresh balance"
                className="flex items-center gap-2 text-right text-xs text-slate-400 hover:text-white transition group">
                <RefreshCw className={cn("h-4 w-4 text-slate-300 transition-transform", refreshing && "animate-spin")} />
                <div className="hidden sm:block">
                  <p className="text-[10px] text-slate-400 font-medium">Last update</p>
                  <p className="font-bold text-slate-300 text-[11px]" data-testid="last-update">
                    {balance ? new Date(balance.at).toLocaleDateString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "27 Oct 10:46 AM"}
                  </p>
                </div>
              </button>
            </div>

            {balanceError && <p className="text-xs text-amber-200">{balanceError}</p>}

            {/* Action buttons row: Add Cash & Cash Out */}
            <div className="grid grid-cols-2 gap-3 pt-1">
              <button
                onClick={onCash}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#38bdf8] hover:bg-[#0ea5e9] text-slate-950 font-black text-xs sm:text-sm shadow-sm transition hover:scale-[1.02] active:scale-95">
                <span className="grid h-5 w-5 place-items-center rounded-full bg-slate-950/15 text-slate-950 text-[10px] font-black">
                  $
                </span>
                Add Cash
              </button>

              <button
                onClick={onRedeem}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-white/10 bg-[#182035] hover:bg-[#1f2942] text-white font-bold text-xs sm:text-sm transition hover:scale-[1.02] active:scale-95">
                <span className="grid h-5 w-5 place-items-center rounded-full bg-white/10 text-white text-[10px] font-bold">
                  $
                </span>
                Cash Out
              </button>
            </div>

            {/* Copyable Account ID box */}
            <div
              onClick={onOpenCreds}
              className="group cursor-pointer rounded-xl border border-white/10 bg-[#182035] hover:bg-[#1f2942] px-4 py-3 flex items-center justify-between transition">
              <span className="font-mono text-sm font-bold text-slate-200" data-testid="field-username">
                {state.account?.username}
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  state.account && copyUsername(state.account.username);
                }}
                className="text-slate-400 hover:text-white transition">
                {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>

            {/* View full login details trigger */}
            <button
              onClick={onOpenCreds}
              className="w-full text-center text-xs font-bold text-sky-400 hover:text-sky-300 hover:underline">
              View login details &amp; password →
            </button>

            {note && (
              <p role={note.tone === "error" ? "alert" : "status"} className={cn("rounded-xl p-3 text-xs", note.tone === "error" ? "bg-rose-500/15 text-rose-200" : "bg-emerald-500/15 text-emerald-100")}>{note.text}</p>
            )}
            {confirming ? (
              <div className="rounded-xl border border-white/15 bg-black/20 p-3" data-testid="confirm-box">
                <p className="text-xs text-slate-200">{confirming === "reset" ? "Set a new password for this login? The old one stops working." : "Remove this login from your list? The game balance must be $0.00. You can get a new login later."}</p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <button disabled={working} data-testid="confirm-yes" onClick={confirming === "reset" ? resetPassword : removeLogin}
                    className={cn("inline-flex h-10 items-center justify-center gap-2 rounded-xl text-xs font-black transition disabled:opacity-50", confirming === "reset" ? "bg-[#38bdf8] text-slate-950 hover:bg-[#0ea5e9]" : "bg-rose-500 text-white hover:bg-rose-400")}>
                    {working && <Spinner className="h-3.5 w-3.5" />}{confirming === "reset" ? "Reset" : "Remove"}
                  </button>
                  <button disabled={working} onClick={() => setConfirming(null)} className="h-10 rounded-xl border border-white/20 text-xs font-bold text-white hover:bg-white/10">Cancel</button>
                </div>
              </div>
            ) : (
              <div className="flex gap-2">
                <button onClick={() => { setNote(null); setConfirming("reset"); }} className="h-11 flex-1 rounded-xl bg-white/10 text-xs font-bold text-white transition hover:bg-white/15 sm:text-sm">Reset password</button>
                <button onClick={() => { setNote(null); setConfirming("remove"); }} aria-label="Remove login" data-testid="remove-login"
                  className="grid h-11 w-12 place-items-center rounded-xl bg-rose-500/15 text-rose-300 transition hover:bg-rose-500/25"><Trash2 className="h-4 w-4" /></button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* RIGHT COLUMN: Promo Banner + Transactions (Screenshot 1) */}
      <div className="flex flex-col gap-4">
        {/* Test your luck promo banner: Loss Streak Diamond Shield */}
        <TestYourLuckBanner />

        {/* Transactions area */}
        <div className="min-h-[280px] rounded-2xl border border-white/10 bg-[#121829] p-8 flex flex-col items-center justify-center text-center">
          <div className="grid h-16 w-16 place-items-center rounded-3xl bg-white/5 border border-white/10 text-slate-400 mb-3">
            <FileText className="h-8 w-8 stroke-[1.5]" />
          </div>
          <p className="text-sm font-semibold text-slate-400">
            Your transactions will be displayed here
          </p>
          <p className="text-xs text-slate-400 mt-1 max-w-xs">
            Recent deposits, redeems, and play sessions appear here automatically.
          </p>
        </div>
      </div>
    </div>
  );
}

/** Login details modal popup (Matches Screenshot 4) */
function LoginDetailsModal({
  slug, game, onCash, onClose
}: {
  slug: string; game: Access["game"]; onCash: () => void; onClose: () => void;
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
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/80 p-4 backdrop-blur-md"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      
      <div className="w-full max-w-sm rounded-3xl border border-white/15 bg-[#131927] p-6 text-white shadow-2xl relative animate-in fade-in zoom-in-95 duration-200">
        
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

        {/* Game icon and title chip */}
        <div className="mt-4 flex items-center gap-3 rounded-2xl bg-white/5 border border-white/10 p-3">
          <div className="h-10 w-10 shrink-0 overflow-hidden rounded-xl border border-white/10 bg-slate-900">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={coverUrl} alt={game.name} className="h-full w-full object-cover" />
          </div>
          <p className="text-base font-extrabold text-white truncate">{game.name}</p>
        </div>

        {/* Divider */}
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
              <span className="font-mono text-sm font-bold text-white truncate" data-testid="field-username">
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
              <span className="font-mono text-sm font-bold text-white truncate" data-testid="field-password">
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

function Sandbox({ text }: { text: string | null }) {
  if (!text) return null;
  return <p className="mb-4 flex gap-2 rounded-2xl border border-amber-300/30 bg-amber-300/10 p-3 text-xs text-amber-100"><FlaskConical className="mt-0.5 h-4 w-4 shrink-0" />{text}</p>;
}

function Cash({ state, onClose, onBack, onRedeem, onChanged }: { state: Access; onClose: () => void; onBack: () => void; onRedeem: () => void; onChanged: () => void }) {
  const { min, max, quick } = state.cash;
  const wallet = num(state.wallet_balance), bonus = num(state.bonus_balance);
  const bonusUsable = !!state.bonus_enabled && bonus > 0;
  const lowWallet = !!state.wallet_funded && wallet < 1 && bonusUsable;
  const [source, setSource] = useState<"wallet" | "bonus">(lowWallet ? "bonus" : "wallet");
  const [amount, setAmount] = useState(lowWallet ? Math.min(10, bonus) : (quick[1] ?? 10));
  const [editing, setEditing] = useState(false);
  const [balance, setBalance] = useState<string | null>(null);
  const [balanceError, setBalanceError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<CashResult | null>(null);
  const [short, setShort] = useState(false);
  const attempt = useRef<{ k: string; key: string } | null>(null);

  const refresh = useCallback(async () => {
    setRefreshing(true); setBalanceError(null);
    try { setBalance((await api<{ balance: string }>(`/games/${state.game.slug}/balance`)).balance); }
    catch (e) { setBalance(null); setBalanceError(errorMessage(e)); } finally { setRefreshing(false); }
  }, [state.game.slug]);
  useEffect(() => { refresh(); }, [refresh]);

  const cap = source === "bonus" ? Math.min(Number(max), bonus) : Number(max);
  const clamp = (n: number) => Math.max(0, Math.min(cap, Math.round(n * 100) / 100));
  const valid = source === "bonus" ? amount > 0 && amount <= cap && (amount >= 1 || amount === bonus) : amount >= Number(min) && amount <= Number(max);
  const allowed = source === "bonus" ? bonusUsable : state.cash_enabled;

  const pick = (s: "wallet" | "bonus") => {
    setSource(s); setError(null); setDone(null); setShort(false);
    setAmount(s === "bonus" ? Math.min(10, bonus) : (quick[1] ?? 10));
  };

  const submit = async (override?: { source: "wallet" | "bonus"; amount: number }) => {
    const src = override?.source ?? source, amt = override?.amount ?? amount;
    setBusy(true); setError(null); setDone(null); setShort(false);
    if (override) { setSource(src); setAmount(amt); }
    const k = `${src}:${amt}`;
    if (!attempt.current || attempt.current.k !== k) attempt.current = { k, key: crypto.randomUUID() };
    try {
      const r = await api<CashResult>(`/games/${state.game.slug}/cash`, { method: "POST", body: { amount: amt.toFixed(2), source: src, idempotency_key: attempt.current.key } });
      setDone(r); attempt.current = null; refresh(); onChanged(); notifyWalletChanged();
    } catch (e) { setShort(e instanceof ApiError && e.code === "insufficient_funds" && src === "wallet"); setError(errorMessage(e)); } finally { setBusy(false); }
  };

  return (
    <div className="max-w-md mx-auto">
      <div className="flex items-start justify-between">
        <h2 className="text-xl font-black text-white">Add Cash</h2>
        <button onClick={onClose} aria-label="Close" className="rounded-xl p-1 text-slate-400 hover:text-white"><X className="h-5 w-5" /></button>
      </div>
      <Sandbox text={state.sandbox_notice} />
      
      <div className="mt-4 flex items-center gap-4 rounded-2xl bg-white/5 border border-white/10 p-4">
        <div className="h-14 w-14 shrink-0 overflow-hidden rounded-xl border border-white/10">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={getGameCover(state.game)} alt="" className="h-full w-full object-cover" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between">
            <p className="truncate text-base font-extrabold text-white">{state.game.name}</p>
            <button onClick={onBack} className="text-xs font-bold text-sky-400 hover:underline">Back</button>
          </div>
          <div className="mt-1 flex items-end gap-5 text-xs text-slate-300">
            <div><p className="text-slate-400">Login</p><p className="font-bold text-white">{state.account?.username}</p></div>
            <div><p className="text-slate-400">Balance</p><p className="font-bold text-white" data-testid="balance">{balance !== null ? money2(balance) : "—"}</p></div>
            <button onClick={refresh} aria-label="Refresh balance" className="text-slate-400 hover:text-white"><RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} /></button>
          </div>
        </div>
      </div>
      {balanceError && <p className="mt-2 text-xs text-amber-200">{balanceError}</p>}

      {(state.wallet_funded || bonusUsable) && (
        <div role="group" aria-label="Pay with" className="mt-4 grid grid-cols-2 gap-1 rounded-2xl bg-white/5 border border-white/10 p-1">
          {([["wallet", "Wallet", state.wallet_funded ? money2(wallet) : null], ["bonus", "Bonus", money2(bonus)]] as const).map(([key, label, bal]) => (
            <button key={key} onClick={() => pick(key)} aria-pressed={source === key} disabled={key === "bonus" && !bonusUsable}
              className={cn("rounded-xl px-3 py-2 text-xs sm:text-sm font-bold transition disabled:opacity-40", source === key ? (key === "bonus" ? "bg-[#ffd966] text-slate-950 font-black" : "bg-sky-400 text-slate-950 font-black") : "text-slate-300 hover:bg-white/10")}>
              {label}{bal && <span className="ml-1.5 font-extrabold">{bal}</span>}
            </button>
          ))}
        </div>
      )}

      <p className="mt-4 text-center text-xs font-semibold text-slate-400">Amount{source === "bonus" ? " from bonus balance" : ""}</p>
      <div className="mt-2 flex items-center justify-between rounded-2xl bg-white/5 border border-white/10 px-5 py-3">
        <button onClick={() => setEditing((v) => !v)} aria-label="Edit amount" className="text-sky-400"><Pencil className="h-4 w-4" /></button>
        {editing ? (
          <input autoFocus inputMode="decimal" aria-label="Amount in dollars" value={amount}
            onChange={(e) => setAmount(clamp(Number(e.target.value.replace(/[^0-9.]/g, "")) || 0))}
            onBlur={() => setEditing(false)} className="w-32 bg-transparent text-center text-3xl font-black text-white outline-none" />
        ) : <p className="text-3xl font-black text-white tabular-nums" data-testid="amount">{money(amount)}</p>}
        <button onClick={() => setAmount(0)} aria-label="Clear amount" className="text-slate-400 hover:text-white"><X className="h-5 w-5" /></button>
      </div>

      <div className="mt-3 grid grid-cols-5 gap-1.5">
        {quick.map((q) => <button key={q} onClick={() => setAmount((a) => clamp(a + q))} className="rounded-xl bg-white/5 border border-white/10 py-2.5 text-xs font-black text-sky-400 hover:bg-white/10">+{q}</button>)}
        <button onClick={() => setAmount((a) => clamp(a * 2))} className="rounded-xl bg-white/5 border border-white/10 py-2.5 text-xs font-black text-sky-400 hover:bg-white/10">X2</button>
        <button onClick={() => setAmount(0)} aria-label="Reset amount" className="grid place-items-center rounded-xl bg-rose-500/15 border border-rose-500/20 text-rose-300 hover:bg-rose-500/25"><Trash2 className="h-4 w-4" /></button>
      </div>

      <dl className="mt-4 space-y-1.5 rounded-2xl bg-white/5 border border-white/10 p-3.5 text-xs text-slate-300">
        {state.wallet_funded && <div className="flex justify-between"><dt className="text-slate-400">Wallet balance</dt><dd className="font-bold text-white" data-testid="wallet-funds">{state.wallet_balance !== null && state.wallet_balance !== undefined ? money2(state.wallet_balance) : "—"}</dd></div>}
        {state.bonus_enabled && <div className="flex justify-between"><dt className="text-slate-400">Bonus balance</dt><dd className="font-bold text-[#ffd966]" data-testid="bonus-funds">{money2(bonus)}</dd></div>}
        <div className="flex justify-between"><dt className="text-slate-400">{source === "bonus" ? "From bonus" : "Add cash range"}</dt><dd className="font-bold text-white">{source === "bonus" ? `min ${money(state.bonus_min ?? "1")} or the whole balance` : `${money(min)} – ${money(max)}`}</dd></div>
      </dl>

      {error && <p role="alert" className="mt-3 rounded-2xl bg-rose-500/15 border border-rose-500/20 p-3 text-xs text-rose-200">{error}{short && <button onClick={() => { onClose(); window.dispatchEvent(new Event(OPEN_WALLET_EVENT)); }} className="ml-2 font-bold text-sky-400 underline">Open wallet</button>}</p>}
      {done && (
        <p role="status" className="mt-3 rounded-2xl bg-emerald-500/15 border border-emerald-500/20 p-3 text-xs text-emerald-200">
          {done.status === "completed" ? `${money2(done.amount)} added to game.` : `Request for ${money(done.amount)} received.`}
        </p>
      )}

      <div className="mt-5 grid grid-cols-2 gap-3">
        <button className={btnSky} onClick={() => submit()} disabled={busy || !valid || !allowed}>{busy ? <Spinner /> : null}Add Cash</button>
        <button className={btnDark} onClick={onClose}>Close</button>
      </div>
      <button onClick={onRedeem} className="mt-3 w-full text-center text-xs font-bold text-sky-400 hover:underline">Redeem winnings →</button>
    </div>
  );
}

type RedeemPreview = {
  table: { deposit: string; min: string; max: string }[]; note: string; sandbox: boolean; latest_deposit: string | null;
  rule: { row: number; deposit: string; min: string; max: string } | null; game_balance: string | null; payout: string | null;
  voided: string | null; can_redeem: boolean; needs_confirm: boolean; reason: string | null;
};
type RedeemResult = { status: string; payout: string; voided: string; note: string | null };

function Redeem({ state, onClose, onBack, onChanged }: { state: Access; onClose: () => void; onBack: () => void; onChanged: () => void }) {
  const [p, setP] = useState<RedeemPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RedeemResult | null>(null);
  const [showMatrix, setShowMatrix] = useState(false);
  const key = useRef<string | null>(null);

  const load = useCallback(async () => {
    try { setP(await api<RedeemPreview>(`/games/${state.game.slug}/redeem`)); setError(null); } catch (e) { setError(errorMessage(e)); }
  }, [state.game.slug]);
  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    setBusy(true); setError(null); setResult(null);
    key.current = key.current ?? crypto.randomUUID();
    try {
      const r = await api<RedeemResult>(`/games/${state.game.slug}/redeem`, { method: "POST", body: { idempotency_key: key.current, confirm_void: confirm } });
      setResult(r); key.current = null; setConfirm(false); await load(); onChanged(); notifyWalletChanged();
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  };

  return (
    <div className="max-w-md mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-white/10 pb-3">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-tr from-sky-500 to-emerald-400 text-slate-950 shadow-md">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-xl font-black text-white tracking-wide">Game Cashout</h2>
            <p className="text-xs text-sky-300 font-medium">{state.game.name} · Instant Wallet Transfer</p>
          </div>
        </div>
        <button onClick={onClose} aria-label="Close" className="rounded-xl p-1.5 text-slate-400 hover:text-white hover:bg-white/10 transition">
          <X className="h-5 w-5" />
        </button>
      </div>

      <Sandbox text={state.sandbox_notice} />

      <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-4 text-sm" data-testid="how-cashout">
        <p className="font-bold text-white">How cashout works</p>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-white/70">
          <li>Add cash to this game (from your wallet or your bonus balance) and play.</li>
          <li>The <b>latest cash you added to this game</b> sets how much you can redeem: a minimum and a maximum (see the table below). Adding under $5 does not unlock redeeming.</li>
          <li>Press Cash Out. Your whole game balance leaves the game and the allowed amount is added to your <b>wallet</b>. Anything above the maximum is voided, and you confirm that first.</li>
          <li>One redeem per cash added. To redeem again, add cash to the game again.</li>
          <li>From your wallet you can then cash out to your payment method (minimum $50).</li>
        </ol>
        <p className="mt-3 rounded-xl bg-[#ffd966]/10 p-3 text-[#ffd966]"><b>Bonus balance:</b> it can only be added to a game, never withdrawn directly. Cash added from bonus counts like any other cash added, so the same table and limits apply to what you win with it.</p>
      </div>

      {!p && !error && (
        <div className="grid h-40 place-items-center">
          <div className="flex flex-col items-center gap-2">
            <Spinner className="h-7 w-7 text-sky-400" />
            <span className="text-xs text-slate-400">Loading cashout rules & balance...</span>
          </div>
        </div>
      )}

      {p && (
        <div className="mt-4 space-y-3.5">
          {/* Balance & In-Game Deposit Highlight Cards */}
          <div className="grid grid-cols-2 gap-3">
            <div className="relative overflow-hidden rounded-2xl border border-sky-500/25 bg-gradient-to-br from-[#16213e] to-[#0f172a] p-3.5 shadow-lg">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Game Balance</span>
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              </div>
              <p className="mt-1 text-2xl font-black text-white" data-testid="redeem-balance">
                {p.game_balance !== null ? money2(p.game_balance) : "—"}
              </p>
              <span className="text-[10px] text-sky-400/80">Available in game</span>
            </div>

            <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] p-3.5 shadow-sm">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Game Deposit</span>
              <p className="mt-1 text-2xl font-black text-slate-200">
                {p.latest_deposit ? money2(p.latest_deposit) : "—"}
              </p>
              <span className="text-[10px] text-emerald-400 font-semibold">Sets Cashout Tier</span>
            </div>
          </div>

          {/* Active Rule Pill */}
          {p.rule && (
            <div className="rounded-2xl border border-sky-500/20 bg-sky-500/10 p-3 text-xs text-slate-200" data-testid="redeem-rule">
              <div className="flex items-center gap-1.5 font-bold text-sky-300">
                <Info className="h-4 w-4 shrink-0" />
                <span>Active Tier Rules for ${money2(p.rule.deposit)}:</span>
              </div>
              <p className="mt-1 pl-5 text-[11px] text-slate-300">
                Redeem <b className="text-white">at least {money2(p.rule.min)}</b> and <b className="text-white">at most {money2(p.rule.max)}</b>.
              </p>
            </div>
          )}

          {/* Cashout Outcome Calculation Card */}
          {p.can_redeem ? (
            <div className="rounded-2xl border border-emerald-500/30 bg-gradient-to-br from-emerald-500/15 via-[#13282c] to-[#0d1c24] p-4 shadow-xl">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-emerald-300">Transferring to Wallet</span>
                  <p className="text-xs text-slate-400">Directly into your main balance</p>
                </div>
                <span className="text-2xl font-black text-emerald-300 drop-shadow-[0_0_12px_rgba(52,211,153,0.4)]" data-testid="redeem-payout">
                  +{money2(p.payout ?? 0)}
                </span>
              </div>

              {p.needs_confirm && (
                <div className="mt-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3">
                  <div className="flex justify-between text-xs font-bold text-rose-300">
                    <span>Exceeds Tier Maximum (Voided):</span>
                    <span data-testid="redeem-voided">{money2(p.voided ?? 0)}</span>
                  </div>
                  <label className="mt-2.5 flex cursor-pointer items-start gap-2.5 text-xs text-rose-200">
                    <input
                      type="checkbox"
                      checked={confirm}
                      onChange={(e) => setConfirm(e.target.checked)}
                      data-testid="redeem-confirm"
                      className="mt-0.5 h-4 w-4 rounded accent-rose-500 cursor-pointer"
                    />
                    <span className="leading-tight">
                      I understand {money2(p.voided ?? 0)} above the maximum tier limit will be voided.
                    </span>
                  </label>
                </div>
              )}
            </div>
          ) : p.reason && (
            <div className="rounded-2xl border border-amber-400/25 bg-amber-400/10 p-3.5 text-xs text-amber-200 shadow-sm" data-testid="redeem-reason">
              <div className="flex items-center gap-1.5 font-bold text-amber-300">
                <Info className="h-4 w-4 shrink-0" />
                <span>Cashout Not Available Yet</span>
              </div>
              <p className="mt-1 pl-5 text-amber-100/90 leading-relaxed">{p.reason}</p>
            </div>
          )}

          {/* Collapsible Cashout Limits Matrix */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] overflow-hidden">
            <button
              type="button"
              onClick={() => setShowMatrix((v) => !v)}
              className="w-full flex items-center justify-between p-3.5 text-xs font-bold text-slate-300 hover:text-white transition"
            >
              <span className="flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-sky-400" /> Cashout Rules & Limits Matrix
              </span>
              <span className="text-[10px] font-semibold text-sky-400">
                {showMatrix ? "Hide Matrix ▲" : "View Table ▼"}
              </span>
            </button>

            {showMatrix && (
              <div className="border-t border-white/10 p-3 bg-black/20">
                <table className="w-full text-left text-[11px]">
                  <thead className="text-slate-400 border-b border-white/10">
                    <tr>
                      <th className="py-1.5 font-semibold">Deposit</th>
                      <th className="py-1.5 font-semibold">Minimum</th>
                      <th className="py-1.5 font-semibold">Maximum</th>
                      <th className="py-1.5 text-right font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {p.table.map((row, i) => {
                      const isActive = p.rule?.row === i;
                      return (
                        <tr
                          key={row.deposit}
                          className={cn(
                            "transition",
                            isActive
                              ? "bg-sky-400/20 font-bold text-white border-l-2 border-sky-400"
                              : "text-slate-300 hover:bg-white/5"
                          )}
                        >
                          <td className="py-2 pl-1.5">{row.deposit}</td>
                          <td className="py-2">{row.min}</td>
                          <td className="py-2">{row.max}</td>
                          <td className="py-2 text-right">
                            {isActive ? (
                              <span className="inline-block rounded-full bg-sky-400/30 px-2 py-0.5 text-[9px] font-bold text-sky-300">
                                Active Tier
                              </span>
                            ) : (
                              <span className="text-slate-500">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <p className="mt-2 text-[10px] text-slate-400">
                  * {p.note} Limits are calculated strictly from your in-game deposits.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {error && <p role="alert" className="mt-3 rounded-2xl bg-rose-500/15 p-3 text-xs text-rose-200 border border-rose-500/25">{error}</p>}

      {/* Result celebration */}
      {result && (
        <div
          role="status"
          data-testid="redeem-result"
          className={cn(
            "mt-4 rounded-2xl p-4 text-xs shadow-lg border",
            result.status === "completed"
              ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-200"
              : "border-amber-300/30 bg-amber-300/15 text-amber-100"
          )}
        >
          {result.status === "completed" ? (
            <div className="flex items-center gap-3">
              <div className="grid h-8 w-8 place-items-center rounded-full bg-emerald-400/20 text-emerald-300 shrink-0">
                <Check className="h-4 w-4" />
              </div>
              <div>
                <p className="font-bold text-white text-sm">Cashout Successful!</p>
                <p className="mt-0.5 text-emerald-200">
                  {money2(result.payout)} has been added to your main wallet balance.
                </p>
              </div>
            </div>
          ) : (
            <p>{result.note ?? "Could not complete cashout request."}</p>
          )}
        </div>
      )}

      {/* Action CTA */}
      <div className="mt-5 grid grid-cols-2 gap-3">
        <button
          className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-emerald-400 to-sky-400 hover:from-emerald-300 hover:to-sky-300 text-slate-950 font-black text-sm transition hover:scale-[1.02] active:scale-95 disabled:opacity-50 shadow-lg shadow-emerald-500/20"
          data-testid="redeem-submit"
          onClick={submit}
          disabled={busy || !p?.can_redeem || (p.needs_confirm && !confirm)}
        >
          {busy ? <Spinner className="h-4 w-4 text-slate-950" /> : <Sparkles className="h-4 w-4" />}
          Cash Out to Wallet
        </button>
        <button className={btnDark} onClick={onBack}>
          Back
        </button>
      </div>
    </div>
  );
}

