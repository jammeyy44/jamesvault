"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { motion, useReducedMotion, AnimatePresence } from "framer-motion";
import { Crown, Sparkles, X, ArrowRight } from "lucide-react";
import { Diamond, SparkleField } from "./art";
import { Burst, CountUp } from "./box-opening";
import { cn } from "@/lib/utils";

export type DiamondReward = {
  diamonds: number;
  taskTitle: string;
};

export function DiamondRewardModal({
  reward,
  onClose,
}: {
  reward: DiamondReward | null;
  onClose: () => void;
}) {
  const reduce = useReducedMotion();
  const primaryBtn = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!reward) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    primaryBtn.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [reward, onClose]);

  if (!reward) return null;

  return createPortal(
    <AnimatePresence>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Mission Reward"
        className="fixed inset-0 z-[100] flex items-center justify-center overflow-hidden bg-[#040611]/90 px-4 py-6 text-white backdrop-blur-xl"
      >
        {/* Radial Ambient Glow */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(56,189,248,0.25)_0%,rgba(124,58,237,0.15)_40%,transparent_70%)]" />

        {/* Rotating Sunburst God Rays */}
        {!reduce && (
          <motion.div
            className="pointer-events-none absolute h-[140vmax] w-[140vmax] opacity-35"
            style={{
              background:
                "conic-gradient(from 0deg, transparent 0 8%, rgba(56,189,248,0.4) 10%, transparent 14% 24%, rgba(167,139,250,0.4) 26%, transparent 30% 40%, rgba(56,189,248,0.4) 42%, transparent 46% 56%, rgba(167,139,250,0.4) 58%, transparent 62% 72%, rgba(56,189,248,0.4) 74%, transparent 78% 88%, rgba(56,189,248,0.4) 90%, transparent 94%)",
            }}
            initial={{ opacity: 0, rotate: 0 }}
            animate={{ opacity: 0.35, rotate: 360 }}
            transition={{ opacity: { duration: 0.5 }, rotate: { duration: 50, repeat: Infinity, ease: "linear" } }}
          />
        )}

        {/* Screen flash on entrance */}
        {!reduce && (
          <motion.div
            className="pointer-events-none absolute inset-0 bg-cyan-400"
            initial={{ opacity: 0.6 }}
            animate={{ opacity: 0 }}
            transition={{ duration: 0.6 }}
          />
        )}

        <SparkleField count={28} className="opacity-80" />

        {/* Confetti & Gem Burst */}
        {!reduce && <Burst tone="crystal" />}

        {/* Close Button */}
        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute right-5 top-5 z-20 rounded-full bg-white/10 p-2.5 text-white/70 transition hover:bg-white/20 hover:text-white"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Card Content */}
        <motion.div
          initial={reduce ? false : { scale: 0.6, y: 40, opacity: 0 }}
          animate={{ scale: 1, y: 0, opacity: 1 }}
          exit={{ scale: 0.8, opacity: 0 }}
          transition={{ type: "spring", stiffness: 180, damping: 16 }}
          className="relative z-10 flex w-full max-w-sm flex-col items-center rounded-3xl border border-sky-400/40 bg-gradient-to-b from-[#141b2d]/95 via-[#0d1322]/95 to-[#070b16]/95 p-6 text-center shadow-[0_25px_60px_rgba(0,0,0,0.8),0_0_50px_rgba(56,189,248,0.3)] backdrop-blur-2xl"
        >
          {/* Top Gaming Badge */}
          <motion.div
            initial={reduce ? false : { scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: "spring" }}
            className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-amber-400/50 bg-gradient-to-r from-amber-500/20 to-orange-500/20 px-4 py-1 text-xs font-black uppercase tracking-widest text-amber-300 shadow-[0_0_15px_rgba(251,191,36,0.3)]"
          >
            <Crown className="h-4 w-4 text-amber-400 animate-pulse" />
            <span>MISSION COMPLETED</span>
          </motion.div>

          {/* 3D Giant Shimmering Diamond with Floating Animation */}
          <div className="relative my-3 flex h-36 w-36 items-center justify-center">
            {/* Ambient Diamond Glow Aura */}
            <motion.div
              className="absolute inset-0 rounded-full bg-sky-400/30 blur-2xl"
              animate={reduce ? {} : { scale: [1, 1.25, 1], opacity: [0.5, 0.9, 0.5] }}
              transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
            />
            <motion.div
              animate={reduce ? {} : { y: [0, -8, 0], rotate: [0, 2, -2, 0] }}
              transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut" }}
              className="relative z-10"
            >
              <Diamond size={110} tone="cyan" glow={true} className="drop-shadow-[0_0_30px_rgba(56,189,248,0.8)]" />
            </motion.div>
          </div>

          {/* Reward Amount Rolling */}
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mt-1"
          >
            <span className="block text-4xl sm:text-5xl font-black tracking-tight text-white drop-shadow-[0_4px_12px_rgba(56,189,248,0.5)]">
              +<CountUp to={reward.diamonds} reduce={reduce} /> DIAMONDS
            </span>
          </motion.div>

          {/* Task Source */}
          <div className="mt-2 rounded-xl bg-white/5 border border-white/10 px-3.5 py-1.5">
            <p className="text-xs font-bold text-slate-300">
              Reward from <span className="text-sky-300">{reward.taskTitle}</span>
            </p>
          </div>

          <p className="mt-3 text-xs text-slate-400 font-medium leading-relaxed">
            Diamonds have been credited to your reserve. Use them in the Lucky Shop to crack open secret mystery crates!
          </p>

          {/* High-Voltage CTA Button */}
          <button
            ref={primaryBtn}
            onClick={onClose}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-[#38bdf8] via-[#0ea5e9] to-[#6366f1] py-3.5 text-sm sm:text-base font-black text-slate-950 shadow-[0_0_25px_rgba(56,189,248,0.5)] transition hover:brightness-110 active:scale-95"
          >
            <span>COLLECT REWARD</span>
            <ArrowRight className="h-4 w-4 stroke-[3]" />
          </button>
        </motion.div>
      </div>
    </AnimatePresence>,
    document.body
  );
}
