"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Dice5, Gem, Spade, Sparkles, Trophy } from "lucide-react";
import { cn } from "@/lib/utils";

/** Original hero illustration: layered game cards floating over a soft blue/violet glow. */
export function HeroArt({ className }: { className?: string }) {
  const reduce = useReducedMotion();
  const float = (delay: number, amp = 10) =>
    reduce ? {} : { animate: { y: [0, -amp, 0] }, transition: { duration: 6, repeat: Infinity, ease: "easeInOut" as const, delay } };

  return (
    <div className={cn("relative mx-auto aspect-square w-full max-w-[34rem]", className)} aria-hidden>
      <div className="absolute inset-[8%] rounded-full bg-gradient-to-tr from-primary/30 via-electric/25 to-violet/30 blur-3xl" />
      <div className="absolute inset-[14%] rounded-full border border-primary/15" />
      <div className="absolute inset-[3%] rounded-full border border-dashed border-violet/20" />

      {/* back card */}
      <motion.div {...float(0.4, 8)} className="absolute left-[4%] top-[20%] h-[46%] w-[34%] -rotate-12 rounded-3xl border border-white/30 bg-gradient-to-br from-electric to-primary p-4 shadow-lift">
        <Spade className="h-8 w-8 text-white/90" />
        <div className="absolute bottom-4 right-4 h-16 w-16 rounded-full bg-white/15" />
      </motion.div>

      {/* hero card */}
      <motion.div {...float(0, 12)} className="absolute left-1/2 top-[8%] z-10 h-[58%] w-[44%] -translate-x-1/2 rotate-3 overflow-hidden rounded-3xl border border-white/20 bg-gradient-to-br from-[#1B2A5C] via-[#26308A] to-violet p-5 shadow-lift">
        <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-electric/40 blur-2xl" />
        <Gem className="relative h-10 w-10 text-electric" />
        <div className="relative mt-6 space-y-2">
          <div className="h-2.5 w-3/4 rounded-full bg-white/70" />
          <div className="h-2.5 w-1/2 rounded-full bg-white/35" />
        </div>
        <div className="absolute inset-x-5 bottom-5 flex items-center justify-between">
          <span className="rounded-full bg-white/15 px-3 py-1 text-[0.65rem] font-semibold uppercase tracking-wider text-white">Featured</span>
          <Sparkles className="h-5 w-5 text-white/80" />
        </div>
      </motion.div>

      {/* right card */}
      <motion.div {...float(0.8, 9)} className="absolute right-[2%] top-[48%] z-20 h-[34%] w-[30%] rotate-12 rounded-3xl border border-line bg-white p-4 shadow-lift">
        <Dice5 className="h-8 w-8 text-violet" />
        <div className="mt-4 space-y-2">
          <div className="h-2 w-4/5 rounded-full bg-soft" />
          <div className="h-2 w-3/5 rounded-full bg-soft" />
        </div>
        <div className="absolute bottom-3 right-3 h-8 w-8 rounded-xl bg-brand-gradient" />
      </motion.div>

      {/* chips */}
      <motion.div {...float(1.2, 6)} className="absolute bottom-[10%] left-[14%] z-20 flex items-center gap-2 rounded-2xl border border-line bg-white/90 px-3 py-2 shadow-card backdrop-blur">
        <span className="grid h-8 w-8 place-items-center rounded-xl bg-soft text-primary"><Trophy className="h-4 w-4" /></span>
        <span className="h-2 w-16 rounded-full bg-soft" />
      </motion.div>
      <motion.span {...float(0.2, 5)} className="absolute right-[18%] top-[6%] h-4 w-4 rounded-full bg-success shadow-[0_0_24px_6px_rgba(54,217,138,0.45)]" />
      <motion.span {...float(1, 7)} className="absolute bottom-[22%] right-[8%] h-3 w-3 rounded-full bg-electric shadow-[0_0_20px_5px_rgba(49,156,245,0.5)]" />
    </div>
  );
}
