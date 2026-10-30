"use client";

import { useCallback, useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { motion, useReducedMotion } from "framer-motion";
import { Gift, Lock, Sparkles, Wallet } from "lucide-react";
import { Burst, CountUp } from "./box-opening";
import { DepositBoostBanner, useCountdown, type Boost } from "./deposit-boost";
import { Spinner } from "./ui/bits";
import { OPEN_WALLET_EVENT, notifyWalletChanged } from "./wallet-panel";
import { api, errorMessage } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

type Prize = { id: number; kind: "diamonds" | "freeplay" | "boost_percent"; value: number; title: string; subtitle: string; odds_percent: number; boost_hours: number };
type WheelState = {
  enabled: boolean; reason: string | null; eligible: boolean; can_spin: boolean; closes_in: number | null; next_spin_in: number | null;
  prizes: Prize[]; history: { title: string; subtitle: string; note: string | null; created_at: string }[]; boost: Boost | null;
};
type Result = { prize: Prize; note: string; boost: Boost | null };

const SEG = ["#7c3aed", "#2563eb", "#0d9488", "#c026d3", "#4f46e5", "#0891b2", "#db2777", "#6d28d9"];
const GEM = ["#ffd1f6", "#ff8fe6", "#e83fc8", "#b01fa0", "#7a1275"];  // pink gem facets
const CARD_TONES = ["#ec4899", "#8b5cf6", "#14b8a6", "#3b82f6", "#f43f5e", "#a855f7", "#0ea5e9"];

// ------------------------------------------------------------------ prize glyphs (original SVG, 100x100)
function Gem({ x, y, s, fill = GEM }: { x: number; y: number; s: number; fill?: string[] }) {
  const k = s / 100;  // source gem is 100 wide x 90 tall
  return (
    <g transform={`translate(${x} ${y}) scale(${k})`}>
      <polygon points="5,30 28,8 36,30" fill={fill[1]} /><polygon points="28,8 50,8 36,30" fill={fill[0]} />
      <polygon points="50,8 64,30 36,30" fill={fill[1]} /><polygon points="50,8 72,8 64,30" fill={fill[0]} />
      <polygon points="72,8 95,30 64,30" fill={fill[2]} /><polygon points="5,30 36,30 50,86" fill={fill[3]} />
      <polygon points="36,30 64,30 50,86" fill={fill[2]} /><polygon points="64,30 95,30 50,86" fill={fill[4]} />
      <polyline points="5,30 28,8 72,8 95,30 50,86 5,30" fill="none" stroke="#fff" strokeOpacity=".6" strokeWidth="2" strokeLinejoin="round" />
    </g>
  );
}

function Glyph({ prize, uid, label = false }: { prize: Prize; uid: string; label?: boolean }) {
  if (prize.kind === "diamonds") {
    const n = Math.min(prize.value, 4);
    return (
      <g>
        {n === 1 && <Gem x={20} y={14} s={60} />}
        {n === 2 && <><Gem x={6} y={26} s={50} /><Gem x={40} y={14} s={54} /></>}
        {n === 3 && <><Gem x={4} y={34} s={44} /><Gem x={52} y={34} s={44} /><Gem x={27} y={8} s={48} /></>}
        {n >= 4 && <><Gem x={2} y={38} s={42} /><Gem x={54} y={38} s={42} /><Gem x={8} y={10} s={40} /><Gem x={50} y={8} s={44} /></>}
        {label && <text x="50" y="97" textAnchor="middle" fontSize="20" fontWeight="900" fill="#fff" stroke="#3b0a52" strokeWidth="3" paintOrder="stroke">{prize.value}</text>}
      </g>
    );
  }
  if (prize.kind === "freeplay") {
    return (
      <g>
        <defs><linearGradient id={`sm${uid}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#4f7cff" /><stop offset="1" stopColor="#6d28d9" /></linearGradient>
          <linearGradient id={`tg${uid}`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#ffe08a" /><stop offset="1" stopColor="#f59e0b" /></linearGradient></defs>
        <rect x="12" y="16" width="62" height="64" rx="9" fill={`url(#sm${uid})`} stroke="#c4b5fd" strokeWidth="2" />
        <rect x="12" y="16" width="62" height="14" rx="9" fill="#8b5cf6" />
        <circle cx="26" cy="23" r="2.4" fill="#fde68a" /><circle cx="43" cy="23" r="2.4" fill="#fde68a" /><circle cx="60" cy="23" r="2.4" fill="#fde68a" />
        <rect x="20" y="36" width="46" height="24" rx="4" fill="#fff" />
        {[27, 40, 53].map((x) => <text key={x} x={x} y="55" fontSize="19" fontWeight="900" fill="#e11d48">7</text>)}
        <line x1="76" y1="30" x2="86" y2="30" stroke="#fda4af" strokeWidth="3" /><circle cx="86" cy="30" r="5" fill="#f43f5e" />
        <rect x="44" y="64" width="46" height="24" rx="6" fill={`url(#tg${uid})`} stroke="#fff" strokeOpacity=".7" strokeWidth="1.5" />
        <text x="67" y="82" textAnchor="middle" fontSize="17" fontWeight="900" fill="#4a2a00">${prize.value / 100}</text>
      </g>
    );
  }
  return (  // boost chest
    <g>
      <defs><linearGradient id={`ch${uid}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2dd4bf" /><stop offset="1" stopColor="#0f766e" /></linearGradient></defs>
      <rect x="14" y="44" width="72" height="42" rx="7" fill={`url(#ch${uid})`} stroke="#99f6e4" strokeWidth="2" />
      <path d="M14 48 Q14 22 50 22 Q86 22 86 48 Z" fill="#14b8a6" stroke="#99f6e4" strokeWidth="2" />
      <rect x="14" y="44" width="72" height="6" fill="#0d9488" />
      <rect x="36" y="42" width="28" height="28" rx="5" fill="#fcd34d" stroke="#fff" strokeOpacity=".8" strokeWidth="1.5" />
      <text x="50" y="62" textAnchor="middle" fontSize="15" fontWeight="900" fill="#134e4a">{prize.value}%</text>
    </g>
  );
}

// ------------------------------------------------------------------ the wheel
function WheelArt({ prizes, rotation, locked, reduce }: { prizes: Prize[]; rotation: number; locked: boolean; reduce: boolean | null }) {
  const uid = useId().replace(/:/g, "");
  const n = prizes.length;
  const seg = 360 / n;
  const pt = (deg: number, r: number) => { const a = (deg * Math.PI) / 180; return [200 + r * Math.sin(a), 200 - r * Math.cos(a)]; };
  return (
    <div className={cn("relative aspect-square w-full", locked && "opacity-75 saturate-50")}>
      <motion.div className="absolute inset-0" animate={{ rotate: rotation }} transition={reduce ? { duration: 0 } : { duration: 5.2, ease: [0.12, 0.7, 0.1, 1] }}>
        <svg viewBox="0 0 400 400" className="h-full w-full" aria-hidden>
          {prizes.map((p, i) => {
            const [x0, y0] = pt(i * seg, 176), [x1, y1] = pt((i + 1) * seg, 176);
            const mid = i * seg + seg / 2;
            return (
              <g key={p.id}>
                <path d={n === 1 ? "M200 24A176 176 0 1 1 199.9 24Z" : `M200 200L${x0} ${y0}A176 176 0 ${seg > 180 ? 1 : 0} 1 ${x1} ${y1}Z`} fill={SEG[i % SEG.length]} />
                <path d={`M200 200L${x0} ${y0}`} stroke="#f5c84c" strokeWidth="2.5" />
                <g transform={`rotate(${mid} 200 200) translate(200 ${200 - 128}) translate(-34 -34) scale(.68)`}><Glyph prize={p} uid={`${uid}${i}`} label /></g>
              </g>
            );
          })}
          <circle cx="200" cy="200" r="176" fill="none" stroke="#f5c84c" strokeWidth="3" />
        </svg>
      </motion.div>
      {/* static marquee rim */}
      <svg viewBox="0 0 400 400" className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden>
        <defs><linearGradient id={`rim${uid}`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#ff6ad5" /><stop offset=".5" stopColor="#c026d3" /><stop offset="1" stopColor="#7c1fb8" /></linearGradient></defs>
        <circle cx="200" cy="200" r="188" fill="none" stroke={`url(#rim${uid})`} strokeWidth="24" />
        <circle cx="200" cy="200" r="199" fill="none" stroke="#ffd1f6" strokeOpacity=".5" strokeWidth="2" />
        {Array.from({ length: 28 }, (_, i) => { const [x, y] = pt(i * (360 / 28), 188); return (
          <circle key={i} cx={x} cy={y} r="5.5" fill="#ffe08a" stroke="#fff7d6" strokeWidth="1.2" style={{ filter: "drop-shadow(0 0 5px #ffd24d)", animation: reduce ? undefined : `jvbulb 1.4s ${i % 2 ? "0s" : "0.7s"} infinite alternate` }} />
        ); })}
      </svg>
    </div>
  );
}

function Pointer() {
  return (
    <svg viewBox="0 0 60 78" className="absolute -top-2 left-1/2 z-20 h-16 w-12 -translate-x-1/2 drop-shadow-[0_6px_8px_rgba(0,0,0,.45)]" aria-hidden>
      <defs><linearGradient id="pinG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ffe08a" /><stop offset="1" stopColor="#d98a1a" /></linearGradient></defs>
      <path d="M30 76 C8 52 4 40 4 28 A26 26 0 0 1 56 28 C56 40 52 52 30 76Z" fill="url(#pinG)" stroke="#fff3c4" strokeWidth="2" />
      <circle cx="30" cy="28" r="12" fill="#1d4ed8" stroke="#fff3c4" strokeWidth="2.5" /><circle cx="26" cy="24" r="3.5" fill="#bfdbfe" />
    </svg>
  );
}

const two = (n: number) => String(n).padStart(2, "0");

function TimerPill({ state }: { state: WheelState }) {
  const seconds = state.can_spin ? state.closes_in : state.next_spin_in;
  const { left, h, m, s } = useCountdown(seconds ?? undefined);
  const base = "relative z-10 mx-auto -mt-9 flex w-fit min-w-[14rem] flex-col items-center rounded-full border-[5px] border-[#e8b468] bg-gradient-to-b from-[#8a4a7e] to-[#4b2250] px-10 py-2.5 text-[#ffe2b8] shadow-[0_10px_30px_-8px_rgba(0,0,0,.7),inset_0_2px_0_rgba(255,255,255,.25)]";
  if (seconds != null) {
    return (
      <div className={base} data-testid="wheel-timer">
        <span className="text-[0.68rem] font-bold uppercase tracking-[0.2em] text-[#ffd9a0]/80" data-testid="wheel-timer-label">{state.can_spin ? "Time left to spin" : "Next spin in"}</span>
        <span className="text-3xl font-extrabold tabular-nums leading-tight">{two(h)}:{two(m)}:{two(s)}</span>
        {left <= 0 && <span className="sr-only">Refresh to update</span>}
      </div>
    );
  }
  return (
    <button
      onClick={() => window.dispatchEvent(new Event(OPEN_WALLET_EVENT))}
      className={cn(base, "py-4 cursor-pointer hover:scale-105 active:scale-95 transition-transform duration-200")}
      data-testid="wheel-timer"
      title="Click to open deposit wallet"
    >
      <span className="flex items-center gap-2 text-lg font-extrabold text-[#ffe2b8]">
        <Lock className="h-5 w-5 text-amber-400" />
        Deposit to unlock
      </span>
    </button>
  );
}

// ------------------------------------------------------------------ result modal
function WheelResultModal({ r, onClose }: { r: Result; onClose: () => void }) {
  const reduce = useReducedMotion();
  const uid = useId().replace(/:/g, "");
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow; document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = prev; };
  }, [onClose]);
  const p = r.prize;
  const pal = p.kind === "freeplay" ? "from-[#3b82f6] via-[#4f46e5] to-[#7c3aed]" : p.kind === "boost_percent" ? "from-[#14b8a6] via-[#0d9488] to-[#0f766e]" : "from-[#ec4899] via-[#c026d3] to-[#7c3aed]";
  const amount = p.kind === "freeplay" ? p.value / 100 : p.value;
  return createPortal(
    <div role="dialog" aria-modal="true" aria-label="Free spin result" className="fixed inset-0 z-[60] grid place-items-center overflow-y-auto bg-[#070a1c]/95 p-4 text-white backdrop-blur-md">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_50%_at_50%_40%,rgba(192,38,211,.3),transparent_70%)]" />
      <div className="relative w-full max-w-sm text-center">
        {!reduce && <Burst tone="crystal" />}
        <p className="text-xs font-bold uppercase tracking-[0.3em] text-white/50">Free spin</p>
        <motion.div initial={reduce ? false : { y: 60, scale: 0.6, opacity: 0 }} animate={{ y: 0, scale: 1, opacity: 1 }} transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 140, damping: 13, delay: 0.15 }}
          className={cn("relative mx-auto mt-4 overflow-hidden rounded-3xl bg-gradient-to-br p-px shadow-[0_24px_60px_-12px_rgba(0,0,0,.7)]", pal)}>
          <div className={cn("rounded-[1.4rem] bg-gradient-to-br px-6 py-7", pal)}>
            <p className="text-xs font-bold uppercase tracking-[0.25em] text-white/80">You won</p>
            <svg viewBox="0 0 100 100" className="mx-auto mt-2 h-28 w-28 drop-shadow-lg" aria-hidden><Glyph prize={p} uid={uid} /></svg>
            <p className="mt-1 text-6xl font-black leading-none drop-shadow-[0_4px_0_rgba(0,0,0,.25)]" data-testid="wheel-amount">
              <CountUp to={amount} prefix={p.kind === "freeplay" ? "$" : ""} suffix={p.kind === "boost_percent" ? "%" : ""} reduce={reduce} />
            </p>
            <p className="mt-2 text-xl font-extrabold uppercase tracking-wide">{p.subtitle}</p>
          </div>
        </motion.div>
        <p className="mt-5 flex items-center justify-center gap-1.5 text-sm text-white/85" data-testid="wheel-note"><Sparkles className="h-4 w-4 shrink-0 text-[#ffd966]" />{r.note}</p>
        {r.boost && p.kind === "boost_percent" && <DepositBoostBanner boost={r.boost} className="mt-4 text-left" />}
        <button onClick={onClose} className="mt-5 h-12 w-full rounded-2xl bg-electric font-bold text-ink transition hover:brightness-110">Done</button>
      </div>
    </div>,
    document.body,
  );
}

// ------------------------------------------------------------------ section
export function FreeSpin({ onChanged, showBoost = true }: { onChanged?: () => void; showBoost?: boolean }) {
  const reduce = useReducedMotion();
  const [state, setState] = useState<WheelState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rotation, setRotation] = useState(0);
  const [spinning, setSpinning] = useState(false);
  const [result, setResult] = useState<Result | null>(null);

  const load = useCallback(async () => {
    try { setState(await api<WheelState>("/wheel")); } catch (e) { setError(errorMessage(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (error && !state) return <p role="alert" className="rounded-2xl bg-red-500/15 p-4 text-sm text-red-200">{error}</p>;
  if (!state) return <div className="grid h-48 place-items-center"><Spinner className="h-6 w-6" /></div>;

  const n = state.prizes.length;
  const locked = !state.can_spin;

  const spin = async () => {
    setSpinning(true); setError(null);
    try {
      const r = await api<{ prize: Prize; note: string; state: WheelState }>("/wheel/spin", { method: "POST" });
      const idx = Math.max(0, state.prizes.findIndex((p) => p.id === r.prize.id));
      const seg = 360 / n;
      // land the winning slice under the pointer: the outcome is already decided and saved by the server
      setRotation((prev) => prev - (prev % 360) + 360 * 6 + (360 - (idx * seg + seg / 2)));
      setTimeout(() => {
        setResult({ prize: r.prize, note: r.note, boost: r.state.boost });
        setState(r.state); setSpinning(false); notifyWalletChanged(); onChanged?.();
      }, reduce ? 0 : 5400);
    } catch (e) { setError(errorMessage(e)); setSpinning(false); load(); }
  };

  return (
    <section aria-labelledby="spin-title" className="overflow-hidden rounded-[2rem] border border-white/10 bg-gradient-to-b from-[#1b1466] via-[#150f4d] to-[#0d0a2e] px-4 pb-8 pt-8 text-white shadow-[0_30px_80px_-30px_rgba(150,60,255,.55)] sm:px-8">
      <style>{`@keyframes jvbulb { from { opacity: .35 } to { opacity: 1 } }`}</style>
      <h2 id="spin-title" className="mx-auto max-w-xs text-center text-lg font-extrabold leading-snug sm:text-xl">Spin the wheel and claim your lucky reward</h2>

      {showBoost && state.boost && <DepositBoostBanner boost={state.boost} onExpire={load} className="mx-auto mt-5 max-w-2xl" />}

      {n === 0 ? <p className="mt-8 text-center text-white/60">{state.reason ?? "The wheel is being set up."}</p> : (
        <>
          <div className="relative mx-auto mt-8 w-full max-w-[34rem] overflow-hidden" style={{ aspectRatio: "1 / 0.54" }}>
            <Pointer />
            <div className="absolute inset-x-0 top-3 mx-auto w-full"><WheelArt prizes={state.prizes} rotation={rotation} locked={locked && !spinning} reduce={reduce} /></div>
          </div>
          <TimerPill state={state} />

          <div className="mx-auto mt-5 flex max-w-sm flex-col items-center gap-3 text-center">
            {state.can_spin ? (
              <button onClick={spin} disabled={spinning} data-testid="spin-button"
                className="inline-flex h-14 w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-[#ec4899] to-[#7c3aed] text-lg font-extrabold shadow-[0_14px_34px_-8px_rgba(192,38,211,.9)] transition hover:brightness-110 active:scale-[0.98] disabled:opacity-70">
                {spinning ? <><Spinner className="h-5 w-5" />Spinning…</> : <><Gift className="h-5 w-5" />Spin now</>}
              </button>
            ) : !state.eligible && state.next_spin_in === null && state.enabled ? (
              <>
                <p className="text-sm text-white/75">{state.reason}</p>
                <button onClick={() => window.dispatchEvent(new Event(OPEN_WALLET_EVENT))} data-testid="spin-deposit"
                  className="inline-flex h-14 w-full items-center justify-center gap-2 rounded-2xl bg-electric text-lg font-extrabold text-ink transition hover:brightness-110"><Wallet className="h-5 w-5" />Deposit now</button>
              </>
            ) : (
              <>
                <button
                  onClick={() => window.dispatchEvent(new Event(OPEN_WALLET_EVENT))}
                  data-testid="spin-button"
                  className="inline-flex h-14 w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 text-slate-950 font-black text-lg shadow-[0_10px_25px_rgba(245,158,11,0.35)] transition hover:scale-[1.02] active:scale-[0.98]"
                >
                  <Wallet className="h-5 w-5" />
                  Deposit to unlock
                </button>
                <p className="text-sm text-white/65">{state.reason ?? "Free spins unlock with a deposit."}</p>
              </>
            )}
            {error && <p role="alert" className="w-full rounded-xl bg-red-500/15 px-3 py-2 text-sm text-red-200">{error}</p>}
          </div>

          <div className="mt-10">
            <h3 className="text-center text-xl font-extrabold">Possible Rewards</h3>
            <p className="mt-1 text-center text-xs text-white/50">Prizes are picked at random on our server; the odds are shown on each card.</p>
            <ul className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {state.prizes.map((p, i) => {
                const tone = CARD_TONES[i % CARD_TONES.length];
                return (
                  <li key={p.id} className="rounded-2xl border-2 bg-white/[0.04] p-4 text-center" style={{ borderColor: `${tone}66` }}>
                    <svg viewBox="0 0 100 100" className="mx-auto h-16 w-16" aria-hidden><Glyph prize={p} uid={`g${p.id}`} /></svg>
                    <p className="mt-1 text-2xl font-black">{p.title}</p>
                    <p className="text-sm font-bold" style={{ color: tone }}>{p.subtitle}</p>
                    <p className="mx-auto mt-2 h-1 w-10 rounded-full" style={{ background: tone }} />
                    <p className="mt-2 text-[0.7rem] text-white/45">{p.odds_percent}% chance</p>
                  </li>
                );
              })}
            </ul>
          </div>

          {state.history.length > 0 && (
            <div className="mt-8">
              <h3 className="mb-2 text-sm font-bold text-white/70">Your recent spins</h3>
              <ul className="space-y-1 text-sm text-white/65">
                {state.history.slice(0, 5).map((h, i) => <li key={i}>{formatDate(h.created_at)}: {h.title} {h.subtitle}</li>)}
              </ul>
            </div>
          )}
        </>
      )}
      {result && <WheelResultModal r={result} onClose={() => setResult(null)} />}
    </section>
  );
}
