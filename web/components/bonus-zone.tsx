"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  Check,
  CheckCircle2,
  ChevronDown,
  Flame,
  Gem,
  Lock,
  Mail,
  Users,
  Wallet,
  Gift,
  Sparkles,
  Trophy,
  ArrowRight,
  ShieldCheck,
  Zap,
  Star,
  Layers,
  Crown
} from "lucide-react";
import { BoxArt, Diamond, SparkleField, TreasureScene, type BoxTone } from "./art";
import { BoxOpening, type Reward, type ShopBox } from "./box-opening";
import { DiamondRewardModal, type DiamondReward } from "./diamond-reward-modal";
import { DepositBoostBanner, type Boost } from "./deposit-boost";
import { TestYourLuckBanner } from "./test-your-luck";
import { Spinner } from "./ui/bits";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn, formatDay } from "@/lib/utils";

type Task = {
  key: string;
  title: string;
  description: string | null;
  group: string;
  icon: string | null;
  reward: number;
  state: "claimable" | "claimed" | "locked";
  reason: string | null;
  progress: { done: number; total: number } | null;
  available: number;
};

type Zone = {
  diamonds: number;
  bonus_balance?: string;
  boost?: Boost | null;
  sandbox_notice?: string | null;
  tasks: Task[];
  boxes: (ShopBox & { affordable: boolean })[];
  rewards: (Reward & { created_at: string })[];
  streak: {
    week: { label: string; date: string; today: boolean; future: boolean; claimed: boolean }[];
    task: Task | null;
  };
};

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  mail: Mail,
  users: Users,
  check: CheckCircle2,
  wallet: Wallet,
  gem: Gem,
  flame: Flame,
};

const BOX_RARITY: Record<string, { label: string; badge: string; glow: string }> = {
  gift: {
    label: "COMMON",
    badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    glow: "from-emerald-500/20 via-emerald-600/5",
  },
  crystal: {
    label: "RARE",
    badge: "bg-sky-500/20 text-sky-300 border-sky-500/40",
    glow: "from-sky-500/20 via-sky-600/5",
  },
  gold: {
    label: "EPIC",
    badge: "bg-amber-500/20 text-amber-300 border-amber-500/40",
    glow: "from-amber-500/20 via-amber-600/5",
  },
  ember: {
    label: "LEGENDARY",
    badge: "bg-orange-500/20 text-orange-300 border-orange-500/40",
    glow: "from-orange-500/20 via-orange-600/5",
  },
  emerald: {
    label: "MYTHIC",
    badge: "bg-violet-500/20 text-violet-300 border-violet-500/40",
    glow: "from-violet-500/20 via-purple-600/5",
  },
};

const PREVIEW_BOXES: (ShopBox & { affordable: boolean })[] = [
  { id: 1, name: "Starter Gift", tone: "gift", cost_diamonds: 5, prize_label: "Mystery Prize", prize_kind: "freeplay", description: "Crack open to reveal secret reward.", affordable: false },
  { id: 2, name: "Silver Chest", tone: "crystal", cost_diamonds: 10, prize_label: "Mystery Prize", prize_kind: "freeplay", description: "Crack open to reveal secret reward.", affordable: false },
  { id: 3, name: "Golden Chest", tone: "gold", cost_diamonds: 15, prize_label: "Mystery Prize", prize_kind: "freeplay", description: "Crack open to reveal secret reward.", affordable: false },
  { id: 4, name: "Crystal Vault", tone: "ember", cost_diamonds: 20, prize_label: "Mystery Prize", prize_kind: "deposit_bonus_percent", description: "Crack open to reveal secret reward.", affordable: false },
  { id: 5, name: "Emerald Treasure", tone: "emerald", cost_diamonds: 30, prize_label: "Mystery Prize", prize_kind: "bonus_cash", description: "Crack open to reveal secret reward.", affordable: false },
];

const PREVIEW_TASKS: Task[] = [
  { key: "daily_login", title: "Daily Login", description: "Visit every day and claim shining diamonds.", group: "daily", icon: "check", reward: 1, state: "claimable", reason: null, progress: null, available: 1 },
  { key: "daily_deposit", title: "Daily Deposit", description: "Make a deposit of $20 or more today and get your diamond reward.", group: "daily", icon: "wallet", reward: 2, state: "locked", reason: "Requires $20+ deposit", progress: null, available: 0 },
  { key: "first_deposit", title: "First Deposit", description: "Make your first deposit and claim a diamond bonus.", group: "daily", icon: "gem", reward: 5, state: "locked", reason: "One-time bonus", progress: null, available: 0 },
  { key: "verify_email", title: "Confirm Email", description: "Confirm your email address to receive diamond prizes.", group: "general", icon: "mail", reward: 2, state: "claimable", reason: null, progress: null, available: 1 },
  { key: "refer_friend", title: "Refer Friends", description: "Earn diamonds for every friend whose sign-up we confirm.", group: "general", icon: "users", reward: 3, state: "claimable", reason: null, progress: null, available: 1 },
];

const REWARD_STATUS: Record<string, { label: string; cls: string }> = {
  applied: { label: "Active in Balance", cls: "bg-emerald-400/20 text-emerald-300 border border-emerald-400/30" },
  available: { label: "Active in Balance", cls: "bg-emerald-400/20 text-emerald-300 border border-emerald-400/30" },
  fulfilled: { label: "Active in Balance", cls: "bg-emerald-400/20 text-emerald-300 border border-emerald-400/30" },
  void: { label: "Cancelled", cls: "bg-white/10 text-white/50 border border-white/10" },
};

// ------------------------------------------------------------------ Poster (Hero)
function Poster({ diamonds, bonusBalance, streakDays }: { diamonds: number | null; bonusBalance?: string; streakDays?: number }) {
  const reduce = useReducedMotion();
  return (
    <section
      aria-label="Bonus Zone Hero"
      className="relative overflow-hidden rounded-[1.75rem] sm:rounded-[2.25rem] border border-white/20 bg-gradient-to-r from-[#171438] via-[#2c1d56] to-[#4338ca] shadow-[0_20px_50px_rgba(0,0,0,0.6)] min-h-[15rem] xs:min-h-[16.5rem] sm:min-h-[19rem] md:min-h-[22rem] flex flex-col justify-center p-4 sm:p-7 md:p-10"
    >
      <SparkleField count={16} className="opacity-70" />

      {/* Ambient radial glow */}
      <div className="pointer-events-none absolute -right-20 top-1/2 -translate-y-1/2 h-72 w-72 rounded-full bg-violet-500/20 blur-3xl" />

      {/* Text content strictly within 54% width */}
      <div className="relative z-20 w-[54%] sm:w-[54%] lg:w-[50%] pb-1 sm:pb-3">
        {/* VIP Badge */}
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-1.5 sm:mb-2 inline-flex items-center gap-1.5 rounded-full border border-violet-400/30 bg-violet-500/20 px-2.5 py-0.5 text-[9px] sm:text-xs font-black uppercase tracking-wider text-violet-300 backdrop-blur-md w-fit"
        >
          <Crown className="h-3 w-3 text-amber-400" />
          <span>REWARDS VAULT</span>
        </motion.div>

        <h1 className="text-base xs:text-lg sm:text-2xl md:text-3xl lg:text-4xl font-black text-white leading-[1.08] tracking-tight drop-shadow-md">
          STAKESWEEP <br />
          <span className="bg-gradient-to-r from-[#a78bfa] via-[#38bdf8] to-[#4df0a8] bg-clip-text text-transparent">
            BONUS ZONE
          </span>
        </h1>

        <p className="mt-1 text-[11px] xs:text-xs sm:text-base font-extrabold text-violet-200 line-clamp-2">
          Complete daily quests &amp; crack mystery crates for instant freeplay.
        </p>

        {/* Compact stats row */}
        <div className="mt-2 sm:mt-3 flex flex-wrap items-center gap-1.5 text-[10px] sm:text-xs font-bold" aria-live="polite">
          <div className="flex items-center gap-1 rounded-lg bg-[#0E1322]/80 border border-sky-400/30 px-2 sm:px-2.5 py-1 text-sky-300 shadow-sm backdrop-blur-md" data-testid="diamond-balance">
            <Diamond size={14} glow={false} />
            <span className="font-black text-white">{diamonds !== null ? diamonds : 0}</span>
            <span className="text-[9px] uppercase tracking-wide opacity-80">💎 Reserve</span>
          </div>

          {bonusBalance !== undefined && (
            <div className="flex items-center gap-1 rounded-lg bg-[#0E1322]/80 border border-amber-400/30 px-2 sm:px-2.5 py-1 text-amber-300 shadow-sm backdrop-blur-md" data-testid="zone-bonus-balance">
              <Wallet className="h-3 w-3 text-amber-400" />
              <span className="font-black text-[#ffd966] tabular-nums">${Number(bonusBalance).toFixed(2)}</span>
            </div>
          )}

          {streakDays !== undefined && streakDays > 0 && (
            <div className="flex items-center gap-1 rounded-lg bg-orange-500/15 border border-orange-500/30 px-2 sm:px-2.5 py-1 text-orange-300 shadow-sm backdrop-blur-md font-black">
              <Flame className="h-3 w-3 text-amber-400 animate-pulse" />
              <span>{streakDays}D STREAK</span>
            </div>
          )}
        </div>
      </div>

      {/* Hostess Model Cutout - Fits height proportionally with zero clipping of head */}
      <div className="pointer-events-none absolute bottom-0 right-0 sm:right-3 lg:right-6 z-10 h-[92%] sm:h-[95%] w-[46%] sm:w-[42%] max-w-[340px] flex items-end justify-end select-none">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/images/bonus_girl.webp"
          alt="StakeSweep Bonus Zone Hostess"
          className="h-full w-auto max-h-full object-contain object-bottom drop-shadow-[0_15px_30px_rgba(0,0,0,0.65)]"
        />
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ Tasks
function TaskCard({ t, busy, onClaim }: { t: Task; busy: boolean; onClaim: (t: Task) => void }) {
  const Icon = ICONS[t.icon ?? ""] ?? Gem;
  const claimed = t.state === "claimed";
  const claimable = t.state === "claimable";

  return (
    <article
      className={cn(
        "group relative flex flex-col rounded-2xl border border-white/10 bg-[#121827]/90 p-5 shadow-card backdrop-blur-md transition-all duration-300 hover:border-violet-500/40 hover:shadow-[0_10px_30px_rgba(124,58,237,0.15)]",
        claimed && "opacity-60 border-white/5",
        claimable && "border-sky-400/40 bg-gradient-to-b from-[#141e33] to-[#121827]"
      )}
    >
      <header className="flex items-center gap-3 border-b border-white/10 pb-3.5">
        <span className={cn(
          "grid h-11 w-11 place-items-center rounded-xl text-white shadow-md border transition group-hover:scale-105",
          claimable
            ? "bg-gradient-to-br from-[#38bdf8] to-[#0ea5e9] border-sky-300 text-slate-950"
            : claimed
            ? "bg-white/10 border-white/15 text-slate-400"
            : "bg-gradient-to-br from-[#7c3aed] to-[#4f46e5] border-white/20"
        )}>
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-black text-white truncate">{t.title}</h3>
            {t.available > 1 && (
              <span className="rounded-full bg-sky-400/20 border border-sky-400/30 px-2 py-0.5 text-[10px] font-bold text-sky-300">
                {t.available}x ready
              </span>
            )}
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            {t.group === "daily" ? "Daily Mission" : "Vault Quest"}
          </span>
        </div>
      </header>

      <p className="mt-3.5 flex-1 text-xs sm:text-sm text-slate-300 leading-relaxed font-medium">
        {t.description}
      </p>

      {t.progress && t.state !== "claimed" && (
        <div className="mt-3" aria-label={`Progress ${t.progress.done} of ${t.progress.total}`}>
          <div className="flex justify-between text-[11px] font-bold text-slate-400 mb-1">
            <span>Mission Progress</span>
            <span className="text-sky-300">{t.progress.done} / {t.progress.total}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-gradient-to-r from-sky-400 via-cyan-400 to-violet-500 transition-all duration-500"
              style={{ width: `${Math.min(100, (t.progress.done / t.progress.total) * 100)}%` }}
            />
          </div>
        </div>
      )}

      <footer className="mt-4 flex items-stretch overflow-hidden rounded-xl bg-black/40 border border-white/10">
        <button
          onClick={() => onClaim(t)}
          disabled={!claimable || busy}
          aria-label={`${claimed ? "Claimed" : "Claim"} ${t.title}`}
          title={t.state === "locked" ? t.reason ?? undefined : undefined}
          className={cn(
            "flex-1 py-3 text-center text-xs sm:text-sm font-black transition relative overflow-hidden",
            claimable
              ? "bg-[#38bdf8] hover:bg-[#0ea5e9] text-slate-950 shadow-[0_0_15px_rgba(56,189,248,0.35)] active:scale-[0.99]"
              : claimed
              ? "bg-white/10 text-white/70 cursor-default"
              : "bg-white/5 text-white/40 cursor-not-allowed"
          )}
        >
          {busy ? (
            <Spinner className="mx-auto h-4 w-4" />
          ) : claimed ? (
            <span className="inline-flex items-center gap-1.5"><Check className="h-4 w-4 text-emerald-400 stroke-[3]" /> Completed</span>
          ) : claimable ? (
            <span className="inline-flex items-center gap-1 text-slate-950">Claim Reward <ArrowRight className="h-3.5 w-3.5" /></span>
          ) : (
            <span className="inline-flex items-center gap-1.5"><Lock className="h-3.5 w-3.5 text-slate-400" /> Locked</span>
          )}
        </button>
        <span className="flex items-center gap-1.5 px-4 text-xs sm:text-sm font-black text-sky-300 bg-sky-500/10 border-l border-white/10">
          <Diamond size={16} glow={false} />+{t.reward}
        </span>
      </footer>

      {t.state === "locked" && t.reason && (
        <p className="mt-2 text-[11px] text-slate-400 font-medium">Requirement: {t.reason}</p>
      )}
    </article>
  );
}

// ------------------------------------------------------------------ Streak
function Streak({ s, busy, onClaim }: { s: Zone["streak"]; busy: boolean; onClaim: (t: Task) => void }) {
  const done = s.week.filter((d) => d.claimed).length;
  const t = s.task;

  return (
    <aside className="rounded-2xl border border-white/10 bg-[#121827]/90 p-5 shadow-card backdrop-blur-md" aria-label="Weekly streak">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Flame className="h-5 w-5 text-amber-400 animate-pulse" />
          <h3 className="text-base font-black text-white">7-Day Hot Streak</h3>
        </div>
        <span className="rounded-full bg-amber-400/15 border border-amber-400/30 px-2.5 py-0.5 text-[11px] font-black text-amber-300">
          {done}/7 DAYS
        </span>
      </div>

      <p className="text-xs text-slate-400 leading-relaxed font-medium">
        Log in daily to keep your streak alive and unlock the grand 7-day chest bonus.
      </p>

      {/* 7 Days tracker */}
      <div className="mt-4 flex justify-between gap-1.5">
        {s.week.map((d) => (
          <div key={d.date} className="flex flex-1 flex-col items-center gap-1.5" aria-label={`${d.label}${d.claimed ? " claimed" : d.today ? " today" : ""}`}>
            <span
              className={cn(
                "grid h-9 w-9 place-items-center rounded-xl text-xs font-black transition-all",
                d.claimed
                  ? "bg-gradient-to-br from-[#38bdf8] to-[#0ea5e9] text-slate-950 shadow-[0_0_12px_rgba(56,189,248,0.4)]"
                  : d.today
                  ? "border-2 border-amber-400 text-amber-400 bg-amber-500/15 animate-pulse"
                  : "bg-white/5 text-slate-500 border border-white/5"
              )}
            >
              {d.claimed ? <Check className="h-4 w-4 stroke-[3]" /> : d.label[0]}
            </span>
            <span className={cn("h-1 w-full rounded-full transition-all", d.claimed ? "bg-sky-400" : d.today ? "bg-amber-400" : "bg-white/10")} />
            <span className={cn("text-[10px] font-bold", d.today ? "text-amber-400" : "text-slate-400")}>{d.label}</span>
          </div>
        ))}
      </div>

      {/* 7-Day Chest Callout */}
      {t && (
        <div className="mt-5 rounded-xl border border-amber-400/30 bg-gradient-to-br from-amber-500/15 via-[#181622] to-[#0B0E17] p-4 shadow-inner">
          <div className="flex items-center justify-between text-xs sm:text-sm">
            <div className="flex items-center gap-2">
              <Trophy className="h-4 w-4 text-amber-400" />
              <span className="font-black text-white">7-Day Streak Chest</span>
            </div>
            <span className="flex items-center gap-1.5 font-black text-amber-300">
              <Diamond size={16} glow={false} />+{t.reward}
            </span>
          </div>
          <p className="mt-1.5 text-[11px] text-slate-300 font-medium">{done} of 7 days completed this week</p>

          <button
            onClick={() => onClaim(t)}
            disabled={t.state !== "claimable" || busy}
            aria-label="Claim weekly streak"
            className={cn(
              "mt-3 w-full rounded-xl py-2.5 text-xs sm:text-sm font-black transition shadow-sm",
              t.state === "claimable"
                ? "bg-gradient-to-r from-amber-400 to-orange-500 hover:brightness-110 text-slate-950 shadow-[0_0_20px_rgba(251,191,36,0.35)]"
                : "bg-white/5 text-slate-500 cursor-not-allowed border border-white/5"
            )}
          >
            {t.state === "claimed" ? "Claimed this week ✓" : t.state === "claimable" ? "Claim Streak Bonus 💎" : "Complete 7 Days to Unlock"}
          </button>
        </div>
      )}
    </aside>
  );
}

// ------------------------------------------------------------------ Lucky Shop (Crates)
function BoxCard({
  b,
  diamonds,
  onOpen,
  isGuest
}: {
  b: ShopBox & { affordable: boolean };
  diamonds: number;
  onOpen: () => void;
  isGuest?: boolean;
}) {
  const reduce = useReducedMotion();
  const rarity = BOX_RARITY[b.tone] ?? BOX_RARITY.gift;

  return (
    <motion.article
      whileHover={reduce ? undefined : { y: -6, scale: 1.02 }}
      className="group relative flex flex-col items-center overflow-hidden rounded-2xl border border-white/10 bg-[#121827]/90 px-4 pb-5 pt-4 text-center transition-all duration-300 hover:border-violet-500/50 hover:shadow-[0_15px_35px_rgba(0,0,0,0.6)] backdrop-blur-md"
    >
      {/* Ambient background glow matching box tone */}
      <div className={cn("pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b to-transparent opacity-40 transition-opacity duration-300 group-hover:opacity-80", rarity.glow)} />

      {/* Rarity Tag */}
      <div className="relative mb-1 flex items-center justify-between w-full">
        <span className={cn("rounded-full border px-2 py-0.5 text-[9px] font-black uppercase tracking-wider", rarity.badge)}>
          {rarity.label}
        </span>
        <span className="text-[10px] font-bold text-slate-400">Box #{b.id}</span>
      </div>

      <h3 className="relative text-sm font-black text-white mt-1">{b.name}</h3>

      {/* 3D Box Illustration */}
      <div className="relative my-2 h-28 w-28 sm:h-32 sm:w-32 transition duration-300 group-hover:scale-110 group-hover:-rotate-2">
        <BoxArt tone={b.tone as BoxTone} className="h-full w-full drop-shadow-[0_10px_20px_rgba(0,0,0,0.5)]" />
      </div>

      {/* Mystery Reward Badge */}
      <div className="relative mb-3.5 w-full rounded-xl bg-black/40 border border-white/5 py-1.5 px-2 text-center">
        <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400">Vault Prize</span>
        <span className="text-xs font-black text-amber-300">Mystery Reward ✦</span>
      </div>

      {/* Action Button */}
      {isGuest ? (
        <Link
          href="/register"
          className="relative mt-auto flex w-full items-center justify-center gap-1.5 rounded-xl border border-white/15 bg-white/5 py-2 text-xs sm:text-sm font-black text-slate-300 transition hover:bg-white/10 hover:border-white/30"
        >
          <Diamond size={15} glow={false} />
          <span>{b.cost_diamonds} 💎 · Join to Open</span>
        </Link>
      ) : (
        <button
          onClick={onOpen}
          disabled={!b.affordable}
          aria-label={`Open ${b.name}`}
          className={cn(
            "relative mt-auto flex w-full items-center justify-center gap-1.5 rounded-xl border py-2 text-xs sm:text-sm font-black transition shadow-sm",
            b.affordable
              ? "border-sky-400 bg-gradient-to-r from-[#38bdf8] to-[#0ea5e9] hover:brightness-110 text-slate-950 shadow-[0_0_15px_rgba(56,189,248,0.3)] active:scale-[0.98]"
              : "border-white/10 bg-white/5 text-slate-400 cursor-not-allowed"
          )}
        >
          <Diamond size={15} glow={false} />
          <span>{b.cost_diamonds}</span>
          <span className="text-[11px] font-bold opacity-80">
            {b.affordable ? "· Open Crate" : `· Need ${b.cost_diamonds - diamonds}`}
          </span>
        </button>
      )}
    </motion.article>
  );
}

function Shop({
  boxes,
  diamonds,
  onOpen,
  isGuest
}: {
  boxes: (ShopBox & { affordable: boolean })[];
  diamonds: number;
  onOpen: (b: ShopBox) => void;
  isGuest?: boolean;
}) {
  return (
    <section aria-labelledby="shop-title" className="mt-12 sm:mt-16">
      <div className="text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-sky-400/30 bg-sky-500/10 px-3 py-1 text-xs font-bold text-sky-300 mb-2">
          <Trophy className="h-3.5 w-3.5" />
          <span>MYSTERY LOOT CRATES</span>
        </div>
        <h2 id="shop-title" className="text-2xl xs:text-3xl sm:text-4xl font-black text-white tracking-tight">
          The Lucky Shop
        </h2>
        <p className="mx-auto mt-2 max-w-xl text-xs sm:text-sm text-slate-300 leading-relaxed font-medium">
          Exchange your earned diamonds for secret mystery crates. Complete your quests, collect diamonds, and crack open crates to unlock surprise rewards.
        </p>
      </div>

      <div className="mt-7 grid grid-cols-2 gap-3.5 sm:gap-4 md:grid-cols-3 lg:grid-cols-5">
        {boxes.map((b) => (
          <BoxCard
            key={b.id}
            b={b}
            diamonds={diamonds}
            onOpen={() => onOpen(b)}
            isGuest={isGuest}
          />
        ))}
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ My Rewards
function MyRewards({ rewards }: { rewards: Zone["rewards"] }) {
  if (rewards.length === 0) return null;
  return (
    <section aria-labelledby="rewards-title" className="mt-12 sm:mt-16">
      <div className="flex items-center gap-2 mb-4">
        <Sparkles className="h-5 w-5 text-sky-400" />
        <h2 id="rewards-title" className="text-xl sm:text-2xl font-black text-white">Vault Unlocks History</h2>
      </div>
      <ul className="grid gap-3 md:grid-cols-2">
        {rewards.map((r) => {
          const st = REWARD_STATUS[r.status] ?? REWARD_STATUS.available;
          return (
            <li key={r.id} className="rounded-2xl border border-white/10 bg-[#121827]/90 flex items-center gap-4 p-4 shadow-sm backdrop-blur-md">
              <BoxArt tone={r.tone as BoxTone} className="h-12 w-12 sm:h-14 sm:w-14 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="truncate font-bold text-sm text-white">{r.label}</p>
                <p className="text-[11px] text-slate-400 font-medium">{r.box} · {formatDay(r.created_at)}</p>
              </div>
              <span className={cn("shrink-0 rounded-full px-2.5 py-0.5 text-xs font-bold", st.cls)}>{st.label}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

// ------------------------------------------------------------------ Signed Out VIP Showcase
function SignedOutView() {
  const steps = [
    { icon: Gem, title: "01. Collect Diamonds", text: "Confirm your email, log in daily, deposit, and invite friends to fill your diamond balance." },
    { icon: Gift, title: "02. Crack Mystery Crates", text: "Exchange diamonds in the Lucky Shop to crack open secret crates and reveal instant rewards." },
    { icon: Wallet, title: "03. Instant Vault Cashout", text: "Rewards apply instantly with zero waiting — start spinning immediately." },
  ];

  return (
    <div className="mt-10 space-y-12">
      {/* 3 Step Roadmap */}
      <div className="grid gap-4 md:grid-cols-3">
        {steps.map(({ icon: Icon, title, text }) => (
          <div key={title} className="rounded-2xl border border-white/10 bg-[#121827]/90 p-6 shadow-sm backdrop-blur-md hover:border-violet-500/40 transition">
            <span className="mb-4 grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-[#7c3aed] to-[#4f46e5] text-white shadow-md border border-white/20">
              <Icon className="h-6 w-6" />
            </span>
            <h3 className="text-base font-black text-white">{title}</h3>
            <p className="mt-2 text-xs sm:text-sm text-slate-300 font-medium leading-relaxed">{text}</p>
          </div>
        ))}
      </div>

      {/* Guest Preview of Crates */}
      <Shop boxes={PREVIEW_BOXES} diamonds={0} onOpen={() => {}} isGuest />

      {/* CTA Banner */}
      <div className="rounded-3xl border border-violet-500/30 bg-gradient-to-r from-[#171233] via-[#1f1947] to-[#0d1b38] p-8 text-center shadow-[0_15px_40px_rgba(124,58,237,0.2)]">
        <h3 className="text-2xl sm:text-3xl font-black text-white">Ready to Start Winning?</h3>
        <p className="mx-auto mt-2 max-w-lg text-sm text-slate-300 font-medium">
          Create your free stakesweep.net account today. Confirm your email and get immediate diamonds to open your very first mystery crate.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link
            href="/register"
            className="inline-flex h-12 items-center rounded-2xl bg-gradient-to-r from-[#7c3aed] via-[#6366f1] to-[#38bdf8] px-8 text-sm font-black text-white shadow-[0_4px_20px_rgba(124,58,237,0.45)] transition hover:scale-105 active:scale-95"
          >
            Create Account
          </Link>
          <Link
            href="/login"
            className="inline-flex h-12 items-center rounded-2xl border border-white/20 bg-white/5 px-8 text-sm font-bold text-white hover:bg-white/10 transition"
          >
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ Main BonusZone
export function BonusZone() {
  const { player, loading } = useAuth();
  const [zone, setZone] = useState<Zone | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [opening, setOpening] = useState<ShopBox | null>(null);
  const [taskTab, setTaskTab] = useState<"all" | "daily" | "general">("all");

  const [claimedReward, setClaimedReward] = useState<DiamondReward | null>(null);

  const load = useCallback(async () => {
    try {
      setZone(await api<Zone>("/bonus"));
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);

  useEffect(() => {
    if (player) load();
    else setZone(null);
  }, [player, load]);

  const claim = async (t: Task) => {
    setBusyKey(t.key);
    setFlash(null);
    try {
      const r = await api<{ diamonds_awarded: number }>(`/bonus/tasks/${t.key}/claim`, { method: "POST" });
      setClaimedReward({ diamonds: r.diamonds_awarded, taskTitle: t.title });
      await load();
      window.dispatchEvent(new Event("jv-wallet-changed"));
    } catch (e) {
      setError(errorMessage(e));
      await load();
    } finally {
      setBusyKey(null);
    }
  };

  const tasksToDisplay = zone
    ? zone.tasks.filter((t) => (taskTab === "all" ? true : t.group === taskTab))
    : [];

  const streakDone = zone?.streak.week.filter((d) => d.claimed).length ?? 0;

  return (
    <div className="bg-[#0B0E17] text-white min-h-screen">
      <div className="container-x py-6 sm:py-10">
        {/* Main Hero Header */}
        <Poster
          diamonds={zone?.diamonds ?? null}
          bonusBalance={zone?.bonus_balance}
          streakDays={streakDone}
        />

        {/* Deposit Boost Banner if active */}
        {zone?.boost && <DepositBoostBanner boost={zone.boost} onExpire={load} className="mt-5" />}

        {/* Test Your Luck: Loss Streak Shield */}
        <TestYourLuckBanner
          className="mt-5"
          onClaimDiamonds={() => {
            load();
            window.dispatchEvent(new Event("jv-wallet-changed"));
          }}
        />

        {loading ? (
          <div className="grid h-48 place-items-center"><Spinner className="h-8 w-8 text-sky-400" /></div>
        ) : !player ? (
          <SignedOutView />
        ) : (
          <>

            {/* Notification / Flash Toast */}
            <div aria-live="polite" className="mt-4 min-h-6">
              {flash && (
                <p role="status" className="inline-flex items-center gap-2 rounded-xl bg-emerald-400/15 border border-emerald-400/30 px-4 py-2.5 text-xs sm:text-sm font-bold text-emerald-200 shadow-md">
                  <Diamond size={16} glow={false} />{flash}
                </p>
              )}
              {error && (
                <p role="alert" className="rounded-xl bg-rose-500/15 border border-rose-500/30 px-4 py-2.5 text-xs sm:text-sm text-rose-200 font-bold">
                  {error}
                </p>
              )}
            </div>

            {!zone ? (
              <div className="grid h-48 place-items-center"><Spinner className="h-8 w-8 text-sky-400" /></div>
            ) : (
              <>
                {/* Tasks & Streak Section */}
                <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_21rem]">
                  <div className="space-y-6">
                    {/* Tasks Filter Header */}
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-4">
                      <div>
                        <h2 className="text-xl sm:text-2xl font-black text-white">Diamond Missions</h2>
                        <p className="text-xs text-slate-400 font-medium">Complete tasks to claim free diamonds</p>
                      </div>

                      <div className="flex rounded-xl bg-white/5 p-1 border border-white/10">
                        <button
                          onClick={() => setTaskTab("all")}
                          className={cn(
                            "rounded-lg px-3 py-1 text-xs font-bold transition",
                            taskTab === "all" ? "bg-[#38bdf8] text-slate-950 shadow-sm" : "text-slate-400 hover:text-white"
                          )}
                        >
                          All ({zone.tasks.length})
                        </button>
                        <button
                          onClick={() => setTaskTab("daily")}
                          className={cn(
                            "rounded-lg px-3 py-1 text-xs font-bold transition",
                            taskTab === "daily" ? "bg-[#38bdf8] text-slate-950 shadow-sm" : "text-slate-400 hover:text-white"
                          )}
                        >
                          Daily ({zone.tasks.filter((t) => t.group === "daily").length})
                        </button>
                        <button
                          onClick={() => setTaskTab("general")}
                          className={cn(
                            "rounded-lg px-3 py-1 text-xs font-bold transition",
                            taskTab === "general" ? "bg-[#38bdf8] text-slate-950 shadow-sm" : "text-slate-400 hover:text-white"
                          )}
                        >
                          Vault Quests ({zone.tasks.filter((t) => t.group === "general").length})
                        </button>
                      </div>
                    </div>

                    {/* Task Grid */}
                    <div className="grid gap-3.5 sm:grid-cols-2">
                      {tasksToDisplay.map((t) => (
                        <TaskCard key={t.key} t={t} busy={busyKey === t.key} onClaim={claim} />
                      ))}
                    </div>
                  </div>

                  {/* Hot Streak Sidebar */}
                  <Streak s={zone.streak} busy={busyKey === "weekly_streak"} onClaim={claim} />
                </div>

                {/* Lucky Shop Mystery Crates */}
                <Shop boxes={zone.boxes} diamonds={zone.diamonds} onOpen={setOpening} />

                {/* Rewards Vault Unlocks */}
                <MyRewards rewards={zone.rewards} />
              </>
            )}
          </>
        )}
      </div>

      {/* Opening Ceremony Modal */}
      {opening && zone && (
        <BoxOpening
          box={opening}
          diamonds={zone.diamonds}
          onClose={() => setOpening(null)}
          onOpened={() => {
            load();
          }}
        />
      )}

      {/* Diamond Claim Animation Popup */}
      {claimedReward && (
        <DiamondRewardModal
          reward={claimedReward}
          onClose={() => setClaimedReward(null)}
        />
      )}
    </div>
  );
}
