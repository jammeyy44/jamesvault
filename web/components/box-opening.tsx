"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Gift, Sparkles, X } from "lucide-react";
import { BoxArt, Diamond, type BoxTone } from "./art";
import { Spinner } from "./ui/bits";
import { DepositBoostBanner, type Boost } from "./deposit-boost";
import { api, ApiError, errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

export type ShopBox = { id: number; name: string; tone: BoxTone; description: string | null; cost_diamonds: number; prize_label: string; prize_kind: string };
export type Reward = { id: number; box: string; tone: BoxTone; kind: string; label: string; value_cents: number | null; value_percent: number | null; status: string };

const GLOW: Record<BoxTone, string> = { gift: "#ff5a5a", crystal: "#7fd8ff", gold: "#ffcc4d", ember: "#ff8a3d", emerald: "#4df0a8" };
const CONFETTI = ["#ffd966", "#6fdcff", "#b794ff", "#ff7ab8", "#6ef3b5", "#ffffff"];

/** Deterministic pseudo-random so the burst looks organic but never differs between renders. */
const rnd = (i: number, salt: number) => { const x = Math.sin(i * 12.9898 + salt * 78.233) * 43758.5453; return x - Math.floor(x); };

export function CountUp({ to, prefix = "", suffix = "", reduce }: { to: number; prefix?: string; suffix?: string; reduce: boolean | null }) {
  const [v, setV] = useState(reduce ? to : 0);
  useEffect(() => {
    if (reduce) { setV(to); return; }
    let raf = 0; const t0 = performance.now();
    const tick = (t: number) => { const p = Math.min(1, (t - t0) / 1100); setV(to * (1 - Math.pow(1 - p, 3))); if (p < 1) raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, reduce]);
  return <>{prefix}{Math.round(v)}{suffix}</>;
}

export function Burst({ tone }: { tone: BoxTone }) {
  const parts = useMemo(() => Array.from({ length: 34 }, (_, i) => {
    const angle = (i / 34) * Math.PI * 2 + rnd(i, 1) * 0.6;
    const dist = 140 + rnd(i, 2) * 190;
    return { x: Math.cos(angle) * dist, y: Math.sin(angle) * dist - 40, r: (rnd(i, 3) - 0.5) * 540, kind: i % 4 === 0 ? "gem" : i % 4 === 1 ? "spark" : "paper",
      color: CONFETTI[i % CONFETTI.length], size: 6 + rnd(i, 4) * 10, delay: rnd(i, 5) * 0.12 };
  }), []);
  return (
    <div className="pointer-events-none absolute left-1/2 top-[38%] h-0 w-0" aria-hidden>
      {parts.map((p, i) => (
        <motion.span key={i} className="absolute block" style={{ left: 0, top: 0, marginLeft: -p.size / 2, marginTop: -p.size / 2 }}
          initial={{ x: 0, y: 0, opacity: 1, scale: 0.4, rotate: 0 }}
          animate={{ x: p.x, y: [0, p.y, p.y + 90], opacity: [1, 1, 0], scale: [0.4, 1, 0.8], rotate: p.r }}
          transition={{ duration: 2.3 + rnd(i, 6) * 0.7, delay: p.delay, ease: "easeOut", times: [0, 0.4, 1] }}>
          {p.kind === "gem" ? <Diamond size={p.size * 2.4} glow={false} tone={i % 8 === 0 ? "violet" : "cyan"} />
            : p.kind === "spark" ? <span className="block rounded-full" style={{ width: p.size, height: p.size, background: GLOW[tone], boxShadow: `0 0 14px 4px ${GLOW[tone]}` }} />
            : <span className="block rounded-[2px]" style={{ width: p.size, height: p.size * 0.55, background: p.color }} />}
        </motion.span>
      ))}
    </div>
  );
}

function RewardCard({ r, reduce }: { r: Reward; reduce: boolean | null }) {
  const big = r.kind === "bonus_cash";
  const pct = r.kind === "deposit_bonus_percent";
  const palette = big ? "from-[#f5b83d] via-[#e8920f] to-[#b45f06]" : pct ? "from-[#ff8a3d] via-[#e8541f] to-[#a82a14]" : "from-[#3b82f6] via-[#4f46e5] to-[#7c3aed]";
  const amount = pct ? (r.value_percent ?? 0) : Math.round((r.value_cents ?? 0) / 100);
  return (
    <motion.div initial={reduce ? false : { y: 70, scale: 0.55, opacity: 0, rotateX: 50 }} animate={{ y: 0, scale: 1, opacity: 1, rotateX: 0 }}
      transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 140, damping: 13, delay: 0.35 }}
      className={cn("relative mx-auto w-full max-w-xs overflow-hidden rounded-3xl bg-gradient-to-br p-px shadow-[0_24px_60px_-12px_rgba(0,0,0,.7)]", palette)} style={{ perspective: 800 }}>
      <div className={cn("relative overflow-hidden rounded-[1.4rem] bg-gradient-to-br px-6 py-7 text-center", palette)}>
        {big && <span className="absolute -right-9 top-4 rotate-45 bg-white px-10 py-1 text-[0.65rem] font-black uppercase tracking-widest text-[#b45f06]">Big bonus</span>}
        <p className="text-xs font-bold uppercase tracking-[0.25em] text-white/80">You won</p>
        <p className="mt-2 text-7xl font-black leading-none text-white drop-shadow-[0_4px_0_rgba(0,0,0,.25)]" data-testid="reward-amount">
          <CountUp to={amount} prefix={pct ? "" : "$"} suffix={pct ? "%" : ""} reduce={reduce} />
        </p>
        <p className="mt-2 text-xl font-extrabold uppercase tracking-wide text-white">{pct ? "Deposit Boost" : r.kind === "freeplay" ? "Free Play" : "Bonus"}</p>
        <p className="mt-1 text-sm text-white/80">from {r.box}</p>
        {!reduce && <motion.span className="pointer-events-none absolute inset-y-0 -left-1/2 w-1/3 -skew-x-12 bg-white/35 blur-md" initial={{ x: "-100%" }} animate={{ x: "520%" }} transition={{ duration: 1.1, delay: 1.1, ease: "easeInOut" }} />}
      </div>
    </motion.div>
  );
}

type Phase = "ready" | "opening" | "revealed" | "error";

export function BoxOpening({ box, diamonds, onClose, onOpened }: { box: ShopBox; diamonds: number; onClose: () => void; onOpened: (diamondsLeft: number) => void }) {
  const reduce = useReducedMotion();
  const [phase, setPhase] = useState<Phase>("ready");
  const [reward, setReward] = useState<Reward | null>(null);
  const [left, setLeft] = useState(diamonds);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [boost, setBoost] = useState<Boost | null>(null);
  const key = useRef<string>(crypto.randomUUID());
  const primary = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && phase !== "opening") onClose(); };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow; document.body.style.overflow = "hidden";
    primary.current?.focus();
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = prev; };
  }, [phase, onClose]);

  const open = async () => {
    setPhase("opening"); setError(null);
    const suspense = new Promise((r) => setTimeout(r, reduce ? 0 : 1700));  // build the anticipation while the server works
    try {
      const [res] = await Promise.all([api<{ reward: Reward; diamonds: number; note: string | null; boost: Boost | null }>(`/bonus/boxes/${box.id}/open`, { method: "POST", body: { idempotency_key: key.current } }), suspense]);
      setReward(res.reward); setNote(res.note); setBoost(res.boost); setLeft(res.diamonds); setPhase("revealed"); onOpened(res.diamonds);
      window.dispatchEvent(new Event("jv-wallet-changed"));  // header / wallet pick up the new bonus balance or boost
    } catch (e) {
      await suspense;
      setError(errorMessage(e));
      if (e instanceof ApiError && e.status !== 0 && e.status < 500) key.current = crypto.randomUUID();  // refused: next try is a fresh request; network/5xx keep the key (no double spend)
      setPhase("error");
    }
  };

  const again = () => { key.current = crypto.randomUUID(); setReward(null); setNote(null); setBoost(null); setPhase("ready"); };
  const glow = GLOW[box.tone];
  const canAgain = left >= box.cost_diamonds;
  const shake = reduce ? {} : { x: [0, -9, 9, -7, 7, -4, 4, 0], rotate: [0, -5, 5, -4, 4, -2, 2, 0], scale: [1, 1.04, 1.07, 1.1, 1.12] };

  return createPortal(
    <div role="dialog" aria-modal="true" aria-label={`Open ${box.name}`} className="fixed inset-0 z-[100] flex flex-col items-center justify-center overflow-y-auto bg-[#040611]/95 px-4 py-8 text-white backdrop-blur-xl">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(90,80,255,.32)_0%,rgba(10,14,35,.6)_60%,transparent_100%)]" />
      {!reduce && phase === "revealed" && (
        <motion.div className="pointer-events-none absolute left-1/2 top-[38%] h-[140vmax] w-[140vmax] -translate-x-1/2 -translate-y-1/2 opacity-40"
          style={{ background: `conic-gradient(from 0deg, transparent 0 8%, ${glow}55 10%, transparent 14% 24%, ${glow}55 26%, transparent 30% 40%, ${glow}55 42%, transparent 46% 56%, ${glow}55 58%, transparent 62% 72%, ${glow}55 74%, transparent 78% 88%, ${glow}55 90%, transparent 94%)` }}
          initial={{ opacity: 0, rotate: 0 }} animate={{ opacity: 0.5, rotate: 360 }} transition={{ opacity: { duration: 0.6 }, rotate: { duration: 50, repeat: Infinity, ease: "linear" } }} />
      )}
      {!reduce && phase === "revealed" && (
        <motion.div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-amber-300 to-sky-300" initial={{ opacity: 0.85 }} animate={{ opacity: 0 }} transition={{ duration: 0.6 }} />
      )}

      {phase !== "opening" && (
        <button onClick={onClose} aria-label="Close" className="absolute right-5 top-5 z-20 rounded-full bg-white/10 p-2.5 text-white/70 transition hover:bg-white/20 hover:text-white"><X className="h-5 w-5" /></button>
      )}

      <div className="relative z-10 flex w-full max-w-md flex-col items-center text-center">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="mb-2 inline-flex items-center gap-1.5 rounded-full border border-violet-400/40 bg-violet-500/15 px-3.5 py-1 text-[11px] font-black uppercase tracking-widest text-violet-300 shadow-[0_0_15px_rgba(167,139,250,0.25)]"
        >
          <Sparkles className="h-3.5 w-3.5 text-amber-400 animate-pulse" />
          <span>MYSTERY VAULT CRATE</span>
        </motion.div>
        <h2 className="mt-1 text-2xl sm:text-3xl font-black text-white">{box.name}</h2>

        {/* the box */}
        <div className="relative mt-8 h-64 w-64 sm:h-72 sm:w-72">
          <motion.div className="absolute inset-4 rounded-full blur-3xl" style={{ background: glow }}
            animate={phase === "opening" && !reduce ? { opacity: [0.3, 0.9, 0.4, 1], scale: [1, 1.3, 1.15, 1.5] } : { opacity: phase === "revealed" ? 0.7 : 0.35 }} transition={{ duration: 1.7 }} />
          <motion.div className="relative h-full w-full" animate={phase === "opening" ? shake : phase === "ready" && !reduce ? { y: [0, -12, 0] } : {}}
            transition={phase === "opening" ? { duration: 0.6, repeat: Infinity } : { duration: 3, repeat: Infinity, ease: "easeInOut" }}>
            <BoxArt tone={box.tone} open={phase === "revealed"} className="h-full w-full drop-shadow-[0_25px_35px_rgba(0,0,0,.75)]" />
          </motion.div>
          {phase === "revealed" && !reduce && <Burst tone={box.tone} />}
        </div>

        <AnimatePresence mode="wait">
          {phase === "ready" && (
            <motion.div key="ready" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, transition: { duration: 0.06 } }} className="mt-6 w-full space-y-3">
              <p className="text-xs sm:text-sm text-slate-300 font-medium">Tap below to crack the seal and unveil your surprise prize.</p>
              <button ref={primary} onClick={open} className="inline-flex h-14 w-full items-center justify-center gap-2.5 rounded-2xl bg-gradient-to-r from-[#38bdf8] via-[#0ea5e9] to-[#7c3aed] text-base sm:text-lg font-black text-slate-950 shadow-[0_0_30px_rgba(56,189,248,0.5)] transition hover:brightness-110 active:scale-[0.98]">
                <Gift className="h-5 w-5" />CRACK CRATE · <Diamond size={22} glow={false} />{box.cost_diamonds}
              </button>
              <p className="text-xs text-slate-400 font-medium">You have <Diamond size={13} glow={false} className="inline" /> {diamonds} diamonds.</p>
            </motion.div>
          )}
          {phase === "opening" && (
            <motion.div key="opening" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.06 } }} className="mt-8 flex flex-col items-center gap-2" role="status">
              <div className="flex items-center gap-2.5 text-lg sm:text-xl font-black text-amber-300 animate-pulse">
                <Spinner className="h-5 w-5 text-amber-400" />
                <span>CRACKING VAULT CRATE...</span>
              </div>
              <p className="text-xs text-slate-400 font-medium">Revealing your secret prize...</p>
            </motion.div>
          )}
          {phase === "revealed" && reward && (
            <motion.div key="revealed" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-2 w-full space-y-5">
              <RewardCard r={reward} reduce={reduce} />
              <motion.div initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduce ? 0 : 1.2 }} className="space-y-3">
                <p className="flex items-center justify-center gap-1.5 text-sm font-bold text-emerald-300" data-testid="reward-note">
                  <Sparkles className="h-4 w-4 shrink-0 text-amber-300" />{note ?? "Applied to your playable balance immediately!"}
                </p>
                {boost && reward.kind === "deposit_bonus_percent" && <DepositBoostBanner boost={boost} />}
                <div className="grid grid-cols-2 gap-3">
                  <button ref={primary} onClick={again} disabled={!canAgain} className="h-12 rounded-2xl bg-gradient-to-r from-[#38bdf8] to-[#0ea5e9] font-black text-slate-950 shadow-[0_0_20px_rgba(56,189,248,0.4)] transition hover:brightness-110 disabled:opacity-40">
                    {canAgain ? "Open Again 🎁" : `Need ${box.cost_diamonds - left} more 💎`}
                  </button>
                  <button onClick={onClose} className="h-12 rounded-2xl border border-white/20 font-black text-white hover:bg-white/10 transition">
                    Done ✓
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
          {phase === "error" && (
            <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-6 w-full space-y-3">
              <p role="alert" className="rounded-2xl bg-rose-500/15 border border-rose-500/30 p-4 text-sm text-rose-200 font-bold">{error}</p>
              <div className="grid grid-cols-2 gap-3">
                <button ref={primary} onClick={() => setPhase("ready")} className="h-12 rounded-2xl bg-sky-400 font-black text-slate-950">Try Again</button>
                <button onClick={onClose} className="h-12 rounded-2xl border border-white/20 font-bold hover:bg-white/10">Close</button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>,
    document.body,
  );
}
