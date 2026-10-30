"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import { X, Sparkles, Trophy } from "lucide-react";
import { FreeSpin } from "./free-spin";

export function TiredOfLosingCard({ className = "" }: { className?: string }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Small attractive card matching user request */}
      <div
        className={`relative overflow-hidden rounded-2xl border border-violet-500/30 bg-gradient-to-r from-[#17122b] via-[#1a1738] to-[#0f1d38] p-4 sm:p-5 shadow-lg transition hover:border-violet-500/50 ${className}`}
      >
        <div className="pointer-events-none absolute -right-10 -bottom-10 h-32 w-32 rounded-full bg-violet-600/15 blur-2xl" />

        <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-3.5">
          <div className="flex items-center gap-3.5">
            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-amber-400 via-orange-500 to-rose-600 text-white shadow-md border border-white/20">
              <span className="text-xl">🎡</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm sm:text-base font-black text-white tracking-tight">
                  Tired of losing? Try Free Spin
                </h3>
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-400/20 border border-amber-400/30 px-2 py-0.5 text-[10px] font-bold text-amber-300">
                  <Sparkles className="h-2.5 w-2.5" /> FREE SPINS
                </span>
              </div>
              <p className="mt-0.5 text-xs text-slate-300 font-medium">
                Spin the lucky wheel now to win instant diamond rewards, freeplay cash &amp; deposit boosts.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setOpen(true)}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-[#38bdf8] hover:from-violet-500 hover:to-[#0ea5e9] text-white font-black px-5 py-2.5 text-xs sm:text-sm shadow-[0_4px_16px_rgba(124,58,237,0.4)] transition hover:scale-105 active:scale-95 whitespace-nowrap shrink-0 self-start sm:self-auto"
          >
            Try Free Spin 🎡
          </button>
        </div>
      </div>

      {/* Modal showing the Lucky Wheel when user clicks Spin */}
      {open && typeof document !== "undefined" && createPortal(
        <div className="fixed inset-0 z-[120] flex items-center justify-center p-3 sm:p-5">
          <div
            className="fixed inset-0 bg-black/80 backdrop-blur-md transition-opacity"
            onClick={() => setOpen(false)}
          />

          <div className="relative z-10 w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-3xl border border-violet-500/30 bg-[#0C1020] p-4 sm:p-7 shadow-[0_25px_60px_rgba(0,0,0,0.8)] text-white">
            <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-4">
              <div className="flex items-center gap-2">
                <span className="text-xl">🎡</span>
                <h2 className="text-base sm:text-lg font-black text-white">Lucky Free Spin Wheel</h2>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="grid h-9 w-9 place-items-center rounded-xl bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <FreeSpin showBoost={true} />
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
