"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, AlertTriangle, ShieldCheck, X, RefreshCw, Gem, Wallet, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { OPEN_WALLET_EVENT } from "./wallet-panel";
import { DiamondRewardModal, type DiamondReward } from "./diamond-reward-modal";

interface LossStreakState {
  losses: number;
  claimable: number;
  is_voided: boolean;
  voided_amount: number;
}

interface TestYourLuckBannerProps {
  className?: string;
  onClaimSuccess?: (amount: number) => void;
  onClaimDiamonds?: (diamonds: number, label: string) => void;
}

export function TestYourLuckBanner({ className, onClaimSuccess, onClaimDiamonds }: TestYourLuckBannerProps) {
  const { player } = useAuth();
  const [streak, setStreak] = useState<LossStreakState>({
    losses: 0,
    claimable: 0,
    is_voided: false,
    voided_amount: 0,
  });
  const [showRules, setShowRules] = useState<boolean>(false);
  const [rewardModal, setRewardModal] = useState<DiamondReward | null>(null);
  const [claiming, setClaiming] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Load server-side loss streak (calculated strictly from deposits without cashout)
  const loadStreak = useCallback(async () => {
    if (!player) return;
    try {
      const data = await api<LossStreakState>("/bonus/loss-streak");
      setStreak(data);
    } catch {
      // ignore
    }
  }, [player]);

  useEffect(() => {
    loadStreak();
  }, [loadStreak]);

  // Listen to wallet changes (e.g. after a deposit or cashout) to re-evaluate streak in real-time
  useEffect(() => {
    const onWalletChange = () => {
      loadStreak();
    };
    window.addEventListener("jv-wallet-changed", onWalletChange);
    return () => window.removeEventListener("jv-wallet-changed", onWalletChange);
  }, [loadStreak]);

  // Handle server-side claim
  const handleClaim = async () => {
    if (streak.claimable <= 0 || claiming) return;
    setClaiming(true);
    setError(null);
    try {
      const res = await api<{ claimed: string; diamonds_awarded: number; diamonds: number; losses: number }>(
        "/bonus/loss-streak/claim",
        { method: "POST" }
      );
      // Show full-screen gaming reward animation
      setRewardModal({
        diamonds: res.diamonds_awarded,
        taskTitle: `${streak.losses} Consecutive Deposits Without Cashout Shield`,
      });
      // Reset local streak state immediately to 0
      setStreak({
        losses: 0,
        claimable: 0,
        is_voided: false,
        voided_amount: 0,
      });
      onClaimSuccess?.(res.diamonds_awarded);
      onClaimDiamonds?.(res.diamonds_awarded, `${streak.losses} Losses Shield`);
      // Notify entire app of diamond & wallet changes
      window.dispatchEvent(new Event("jv-wallet-changed"));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setClaiming(false);
    }
  };

  const openDeposit = () => {
    window.dispatchEvent(new Event(OPEN_WALLET_EVENT));
  };

  const { losses, claimable, is_voided, voided_amount } = streak;

  return (
    <>
      <div
        className={cn(
          "overflow-hidden rounded-2xl border border-emerald-500/30 bg-gradient-to-r from-[#031d13] via-[#093222] to-[#031d13] p-3 sm:p-4 shadow-[0_10px_30px_rgba(16,185,129,0.15)] text-white transition-all",
          className
        )}
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4">
          
          {/* Left Title & Subtitle with Clover */}
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 sm:h-11 sm:w-11 shrink-0 place-items-center rounded-xl bg-emerald-500/20 border border-emerald-400/40 text-xl sm:text-2xl shadow-inner">
              🍀
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm sm:text-base font-black text-white tracking-tight">Test your luck</h3>
                <span className="rounded-full bg-emerald-400/20 border border-emerald-400/30 px-2 py-0.5 text-[9px] font-black text-emerald-300">
                  DEPOSIT SHIELD
                </span>
              </div>
              <p className="text-[11px] sm:text-xs text-emerald-200/80 font-medium">
                Get diamond bonus if you are unlucky in recent games
              </p>
            </div>
          </div>

          {/* Middle Milestone Progression Nodes: 3 Losses -> 3 💎 | 5 Losses -> 5 💎 | 10 Losses -> 10 💎 */}
          <div className="flex items-center justify-center gap-2 sm:gap-3 py-1 px-2">
            
            {/* Node 1: 3 Losses -> 3 💎 */}
            <div className="flex flex-col items-center">
              <span
                className={cn(
                  "rounded-full px-2 sm:px-2.5 py-0.5 text-[10px] sm:text-xs font-black transition-all",
                  losses >= 3 && !is_voided
                    ? "bg-emerald-400 text-slate-950 shadow-[0_0_12px_rgba(52,211,153,0.7)] scale-105"
                    : "bg-emerald-950/80 border border-emerald-500/30 text-emerald-400"
                )}
              >
                3 💎
              </span>
              <span className="mt-1 text-[9px] sm:text-[10px] font-bold text-emerald-300/70">3 losses</span>
            </div>

            <span className={cn("h-0.5 w-4 sm:w-6 rounded-full transition-all", losses >= 3 && !is_voided ? "bg-emerald-400" : "bg-emerald-900")} />

            {/* Node 2: 5 Losses -> 5 💎 */}
            <div className="flex flex-col items-center">
              <span
                className={cn(
                  "rounded-full px-2 sm:px-2.5 py-0.5 text-[10px] sm:text-xs font-black transition-all",
                  losses >= 5 && !is_voided
                    ? "bg-emerald-400 text-slate-950 shadow-[0_0_12px_rgba(52,211,153,0.7)] scale-105"
                    : "bg-emerald-950/80 border border-emerald-500/30 text-emerald-400"
                )}
              >
                5 💎
              </span>
              <span className="mt-1 text-[9px] sm:text-[10px] font-bold text-emerald-300/70">5 losses</span>
            </div>

            <span className={cn("h-0.5 w-4 sm:w-6 rounded-full transition-all", losses >= 5 && !is_voided ? "bg-emerald-400" : "bg-emerald-900")} />

            {/* Node 3: 10 Losses -> 10 💎 */}
            <div className="flex flex-col items-center">
              <span
                className={cn(
                  "rounded-full px-2 sm:px-2.5 py-0.5 text-[10px] sm:text-xs font-black transition-all",
                  losses >= 10 && !is_voided
                    ? "bg-emerald-400 text-slate-950 shadow-[0_0_12px_rgba(52,211,153,0.7)] scale-105"
                    : "bg-emerald-950/80 border border-emerald-500/30 text-emerald-400"
                )}
              >
                10 💎
              </span>
              <span className="mt-1 text-[9px] sm:text-[10px] font-bold text-emerald-300/70">10 losses</span>
            </div>
          </div>

          {/* Right Action: Claim Button or View More */}
          <div className="flex items-center gap-2 justify-end">
            {claimable > 0 ? (
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={handleClaim}
                disabled={claiming}
                className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-emerald-400 via-teal-300 to-emerald-400 bg-[length:200%_auto] hover:bg-right text-slate-950 font-black text-xs px-3.5 py-2 shadow-[0_0_20px_rgba(52,211,153,0.5)] animate-pulse disabled:opacity-50"
              >
                <Sparkles className="h-3.5 w-3.5" />
                {claiming ? "Claiming..." : `Claim ${claimable} 💎`}
              </motion.button>
            ) : null}

            <button
              onClick={() => setShowRules(true)}
              className="rounded-xl bg-emerald-400 hover:bg-emerald-300 text-slate-950 font-black text-xs px-3.5 py-2 transition shadow-sm shrink-0"
            >
              View more
            </button>
          </div>
        </div>

        {/* Voided Notification Banner */}
        {is_voided && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="mt-2.5 flex items-center justify-between gap-2 rounded-xl bg-amber-500/15 border border-amber-500/30 px-3 py-1.5 text-xs text-amber-200"
          >
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
              <span>
                <strong>Streak Voided:</strong> You completed a cashout! Your previous unclaimed {voided_amount} 💎 were voided.
              </span>
            </div>
            <button
              onClick={openDeposit}
              className="text-[10px] font-bold underline hover:text-white shrink-0"
            >
              Deposit to Start New Streak
            </button>
          </motion.div>
        )}

        {/* Informative Streak Tracker (Automatic from server deposits without cashout) */}
        <div className="mt-2 pt-2 border-t border-emerald-500/15 flex flex-wrap items-center justify-between gap-2 text-[10px] text-emerald-300/70 font-medium">
          <div className="flex items-center gap-2">
            <span>
              Consecutive deposits without cashout: <strong className="text-emerald-300 font-bold">{losses}</strong>
            </span>
            {losses > 0 && losses < 3 && (
              <span className="text-emerald-400/90 font-bold">({3 - losses} more for 3 💎)</span>
            )}
            {losses >= 3 && losses < 5 && (
              <span className="text-emerald-400/90 font-bold">(Claim 3 💎 or {5 - losses} more for 5 💎)</span>
            )}
            {losses >= 5 && losses < 10 && (
              <span className="text-emerald-400/90 font-bold">(Claim 5 💎 or {10 - losses} more for 10 💎)</span>
            )}
            {losses >= 10 && (
              <span className="text-emerald-400/90 font-bold">(MAX 10 💎 Unlocked!)</span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={openDeposit}
              className="inline-flex items-center gap-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/30 px-2 py-0.5 text-emerald-200 font-bold transition hover:scale-105 active:scale-95"
            >
              <Wallet className="h-3 w-3" />
              Deposit to build streak
            </button>
          </div>
        </div>

        {error && (
          <p className="mt-2 text-xs font-bold text-rose-300 bg-rose-500/20 rounded-lg p-2 border border-rose-500/30">
            {error}
          </p>
        )}
      </div>

      {/* Rules Modal */}
      <AnimatePresence>
        {showRules && (
          <div
            role="dialog"
            aria-modal="true"
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-4 backdrop-blur-md"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="w-full max-w-md rounded-3xl border border-emerald-500/30 bg-[#071d15] p-6 text-white shadow-2xl relative"
            >
              <button
                onClick={() => setShowRules(false)}
                className="absolute right-4 top-4 rounded-xl bg-white/10 p-1.5 text-white/70 hover:bg-white/20 hover:text-white transition"
              >
                <X className="h-4 w-4" />
              </button>

              <div className="flex items-center gap-3 mb-4">
                <span className="grid h-12 w-12 place-items-center rounded-2xl bg-emerald-500/20 text-2xl border border-emerald-400/30">
                  🍀
                </span>
                <div>
                  <h3 className="text-lg font-black text-white">Test Your Luck Rules</h3>
                  <p className="text-xs text-emerald-300 font-medium">Loss Streak Diamond Shield</p>
                </div>
              </div>

              <div className="space-y-3 text-xs leading-relaxed text-slate-300">
                <div className="rounded-xl bg-emerald-950/60 border border-emerald-500/20 p-3">
                  <h4 className="font-bold text-emerald-300 flex items-center gap-1.5 mb-1">
                    <ShieldCheck className="h-4 w-4" /> 1. Automatic Deposit Counting
                  </h4>
                  <p>Loss streak is automatically calculated from how many deposits you make without cashing out.</p>
                </div>

                <div className="rounded-xl bg-emerald-950/60 border border-emerald-500/20 p-3">
                  <h4 className="font-bold text-emerald-300 flex items-center gap-1.5 mb-1">
                    <Gem className="h-4 w-4" /> 2. Tiered Diamond Rewards
                  </h4>
                  <ul className="list-disc pl-4 space-y-1 text-slate-200">
                    <li><strong>3 Deposits without cashout:</strong> Earn <strong>3 💎 Diamonds</strong>.</li>
                    <li><strong>5 Deposits without cashout:</strong> Earn <strong>5 💎 Diamonds</strong>.</li>
                    <li><strong>10 Deposits without cashout:</strong> Earn <strong>10 💎 Diamonds</strong> (Max tier).</li>
                  </ul>
                </div>

                <div className="rounded-xl bg-emerald-950/60 border border-emerald-500/20 p-3">
                  <h4 className="font-bold text-emerald-300 flex items-center gap-1.5 mb-1">
                    <RefreshCw className="h-4 w-4" /> 3. Claim &amp; Restart
                  </h4>
                  <p>When you claim your diamonds, your streak restarts from the beginning (0). Your diamonds are permanently saved to your account.</p>
                </div>

                <div className="rounded-xl bg-amber-500/10 border border-amber-500/30 p-3">
                  <h4 className="font-bold text-amber-300 flex items-center gap-1.5 mb-1">
                    <AlertTriangle className="h-4 w-4" /> 4. Void on Win / Cashout
                  </h4>
                  <p className="text-amber-200/90">
                    If you achieve a winning round and cash out after 3 or more attempts <strong>before claiming</strong>, your streak ends and all unclaimed streak diamonds are <strong>voided</strong>.
                  </p>
                </div>
              </div>

              <div className="mt-5 flex gap-2">
                <button
                  onClick={() => {
                    setShowRules(false);
                    openDeposit();
                  }}
                  className="flex-1 rounded-2xl bg-gradient-to-r from-emerald-400 to-teal-400 text-slate-950 font-black py-2.5 text-sm transition shadow-md hover:brightness-110"
                >
                  Deposit Now
                </button>
                <button
                  onClick={() => setShowRules(false)}
                  className="rounded-2xl border border-white/20 bg-white/5 px-4 text-sm font-bold text-white hover:bg-white/10 transition"
                >
                  Close
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Gaming Celebration Animation */}
      <DiamondRewardModal reward={rewardModal} onClose={() => setRewardModal(null)} />
    </>
  );
}
