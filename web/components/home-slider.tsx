"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight, ChevronLeft, ChevronRight, Flame, Sparkles } from "lucide-react";
import { SparkleField, TreasureScene } from "./art";
import { cn } from "@/lib/utils";

const AUTOPLAY_MS = 7500;

export function HomeSlider() {
  const reduce = useReducedMotion();
  const [index, setIndex] = useState(0);
  const [dir, setDir] = useState(1);
  const [paused, setPaused] = useState(false);
  const drag = useRef<number | null>(null);

  // Live countdown timer state
  const [timeLeft, setTimeLeft] = useState({ hours: 7, minutes: 59, seconds: 48 });

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev.seconds > 0) return { ...prev, seconds: prev.seconds - 1 };
        if (prev.minutes > 0) return { ...prev, minutes: 59, seconds: 59 };
        if (prev.hours > 0) return { ...prev, hours: prev.hours - 1, minutes: 59, seconds: 59 };
        return { hours: 23, minutes: 59, seconds: 59 };
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const totalSlides = 3;

  const go = useCallback((next: number, direction?: number) => {
    setDir(direction ?? (next >= index ? 1 : -1));
    setIndex((next + totalSlides) % totalSlides);
  }, [index, totalSlides]);

  useEffect(() => {
    if (reduce || paused) return;
    const t = setTimeout(() => go(index + 1, 1), AUTOPLAY_MS);
    return () => clearTimeout(t);
  }, [index, paused, reduce, go]);

  return (
    <section
      aria-roledescription="carousel"
      aria-label="Featured"
      className="container-x pt-3 sm:pt-5"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <div
        className="group relative overflow-hidden rounded-[1.75rem] sm:rounded-[2.25rem] border border-white/20 bg-[#0E1322] shadow-[0_20px_50px_rgba(0,0,0,0.6)]"
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") go(index + 1, 1);
          if (e.key === "ArrowLeft") go(index - 1, -1);
        }}
        onPointerDown={(e) => { drag.current = e.clientX; }}
        onPointerUp={(e) => {
          if (drag.current !== null) {
            const dx = e.clientX - drag.current;
            if (Math.abs(dx) > 50) go(index + (dx < 0 ? 1 : -1), dx < 0 ? 1 : -1);
          }
          drag.current = null;
        }}
      >
        <AnimatePresence mode="wait" initial={false} custom={dir}>
          {index === 0 ? (
            /* Slide 1: VIP Welcome Pass with Blonde Model */
            <motion.div
              key="welcome-pass"
              custom={dir}
              role="group"
              aria-roledescription="slide"
              initial={reduce ? false : { opacity: 0, x: 40 * dir }}
              animate={{ opacity: 1, x: 0 }}
              exit={reduce ? { opacity: 0 } : { opacity: 0, x: -40 * dir }}
              transition={{ duration: reduce ? 0 : 0.45, ease: "easeOut" }}
              className="relative min-h-[15rem] xs:min-h-[16.5rem] sm:min-h-[19rem] md:min-h-[22rem] lg:min-h-[24rem] overflow-hidden bg-gradient-to-r from-[#4c1d95] via-[#6b21a8] to-[#1e143b] p-4 sm:p-7 md:p-8 lg:p-10 flex flex-col justify-center"
            >
              <SparkleField count={14} className="opacity-60" />

              {/* Text container: Generous width & max-width prevents cutting on desktop */}
              <div className="relative z-20 w-[60%] sm:w-[58%] lg:w-[62%] max-w-2xl pb-2 sm:pb-4">
                <div className="inline-flex items-center gap-1.5 rounded-full bg-amber-400/15 border border-amber-400/30 px-2.5 py-0.5 text-[9px] sm:text-xs font-black text-amber-300 backdrop-blur-md mb-1.5 sm:mb-2 w-fit">
                  <Sparkles className="h-3 w-3 text-amber-300" />
                  <span>VIP WELCOME PASS</span>
                </div>

                <h1 className="text-base xs:text-lg sm:text-2xl md:text-3xl lg:text-[2.25rem] xl:text-4xl font-black text-white leading-[1.12] tracking-tight drop-shadow-md">
                  Double Your First{" "}
                  <br className="hidden xs:inline md:hidden" />
                  <span className="bg-gradient-to-r from-amber-300 via-yellow-200 to-amber-400 bg-clip-text text-transparent">
                    Vault Deposit
                  </span>
                </h1>

                <p className="mt-1 text-[11px] xs:text-xs sm:text-sm md:text-base font-extrabold text-sky-300 drop-shadow-sm">
                  100% Match up to $2,500 + 150 Spins
                </p>

                {/* Capsule Timer */}
                <div className="mt-2 sm:mt-3 flex items-center gap-2">
                  <div className="inline-flex items-center gap-1.5 rounded-xl bg-black/40 border border-amber-400/30 px-2 sm:px-3 py-1 backdrop-blur-md shadow-inner">
                    <Flame className="h-3.5 w-3.5 text-amber-400 animate-bounce" />
                    <span className="text-[8px] sm:text-[10px] font-bold text-slate-300 uppercase tracking-wider">
                      CLOSES IN:
                    </span>
                    <span className="text-[10px] sm:text-xs font-black text-amber-300 tabular-nums">
                      {String(timeLeft.hours).padStart(2, "0")}h {String(timeLeft.minutes).padStart(2, "0")}m {String(timeLeft.seconds).padStart(2, "0")}s
                    </span>
                  </div>
                </div>

                {/* Action buttons */}
                <div className="mt-3 sm:mt-4 flex flex-wrap items-center gap-2 sm:gap-3">
                  <Link
                    href="/bonus-zone"
                    className="inline-flex items-center justify-center rounded-xl sm:rounded-2xl bg-gradient-to-r from-[#38bdf8] to-[#0ea5e9] hover:brightness-110 text-slate-950 font-black px-4 sm:px-6 py-2 sm:py-2.5 text-xs sm:text-sm shadow-[0_6px_20px_rgba(56,189,248,0.45)] transition hover:scale-105 active:scale-95"
                  >
                    Claim Pass <ArrowUpRight className="h-3.5 w-3.5 ml-1 stroke-[3]" />
                  </Link>

                  <div className="hidden xs:flex items-center gap-1.5 text-[9px] sm:text-xs font-bold text-white/80">
                    <span className="rounded-md bg-white/10 px-2 py-0.5 border border-white/10">0% Fee</span>
                    <span className="rounded-md bg-white/10 px-2 py-0.5 border border-white/10">Instant Payout</span>
                  </div>
                </div>
              </div>

              {/* Fast Loading Optimized WebP Cutout */}
              <div className="pointer-events-none absolute bottom-0 right-0 sm:right-2 md:right-4 lg:right-6 xl:right-10 z-10 h-[92%] sm:h-[95%] w-[42%] sm:w-[40%] md:w-[38%] max-w-[320px] lg:max-w-[360px] flex items-end justify-end select-none">
                <picture className="block h-full">
                  <source srcSet="/images/hero_model_blonde.webp" type="image/webp" />
                  <img
                    src="/images/hero_model_blonde.png"
                    alt="VIP Welcome Pass"
                    loading="eager"
                    fetchPriority="high"
                    decoding="async"
                    className="h-full w-auto max-h-full object-contain object-bottom drop-shadow-[0_15px_30px_rgba(0,0,0,0.65)]"
                  />
                </picture>
              </div>
            </motion.div>
          ) : index === 1 ? (
            /* Slide 2: High-Roller Mega Jackpots with Brunette Model */
            <motion.div
              key="high-roller-jackpots"
              custom={dir}
              role="group"
              aria-roledescription="slide"
              initial={reduce ? false : { opacity: 0, x: 40 * dir }}
              animate={{ opacity: 1, x: 0 }}
              exit={reduce ? { opacity: 0 } : { opacity: 0, x: -40 * dir }}
              transition={{ duration: reduce ? 0 : 0.45, ease: "easeOut" }}
              className="relative min-h-[15rem] xs:min-h-[16.5rem] sm:min-h-[19rem] md:min-h-[22rem] lg:min-h-[24rem] overflow-hidden bg-gradient-to-r from-[#071322] via-[#0a2342] to-[#0369a1] p-4 sm:p-7 md:p-8 lg:p-10 flex flex-col justify-center"
            >
              <SparkleField count={12} className="opacity-60" />

              <div className="pointer-events-none absolute -right-20 top-1/2 -translate-y-1/2 h-72 w-72 rounded-full bg-sky-500/10 blur-2xl" />

              <div className="relative z-20 w-[60%] sm:w-[58%] lg:w-[62%] max-w-2xl pb-2 sm:pb-4">
                <div className="inline-flex items-center gap-1.5 rounded-full border border-sky-400/30 bg-sky-500/15 px-2.5 py-0.5 text-[9px] sm:text-xs font-black text-sky-300 backdrop-blur-md mb-1.5 sm:mb-2 w-fit">
                  <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-ping" />
                  <span>HIGH-ROLLER ARENA</span>
                </div>

                <h2 className="text-base xs:text-lg sm:text-2xl md:text-3xl lg:text-[2.25rem] xl:text-4xl font-black text-white leading-[1.12] tracking-tight drop-shadow-md">
                  Unleash Mega{" "}
                  <br className="hidden xs:inline md:hidden" />
                  <span className="bg-gradient-to-r from-sky-400 via-cyan-300 to-teal-300 bg-clip-text text-transparent">
                    Jackpots &amp; Slots
                  </span>
                </h2>

                <p className="mt-1 text-[11px] xs:text-xs sm:text-sm md:text-base font-extrabold text-cyan-200">
                  Certified 98.7% RTP &bull; $120k Won This Week
                </p>

                <div className="mt-2 sm:mt-3 flex items-center gap-1.5 text-[9px] sm:text-xs font-bold text-white/80">
                  <span className="rounded-md bg-white/10 px-2 py-0.5 border border-white/10">6 Providers</span>
                  <span className="rounded-md bg-white/10 px-2 py-0.5 border border-white/10">60-Sec Cashout</span>
                </div>

                <div className="mt-3 sm:mt-4">
                  <Link
                    href="/games"
                    className="inline-flex items-center justify-center rounded-xl sm:rounded-2xl bg-[#38bdf8] hover:bg-[#0ea5e9] text-slate-950 font-black px-4 sm:px-6 py-2 sm:py-2.5 text-xs sm:text-sm shadow-[0_6px_20px_rgba(56,189,248,0.45)] transition hover:scale-105 active:scale-95"
                  >
                    Play High Roller <ArrowUpRight className="h-3.5 w-3.5 ml-1 stroke-[3]" />
                  </Link>
                </div>
              </div>

              {/* Fast Loading Optimized WebP Cutout */}
              <div className="pointer-events-none absolute bottom-0 right-0 sm:right-2 md:right-4 lg:right-6 xl:right-10 z-10 h-[92%] sm:h-[95%] w-[42%] sm:w-[40%] md:w-[38%] max-w-[320px] lg:max-w-[360px] flex items-end justify-end select-none">
                <picture className="block h-full">
                  <source srcSet="/images/hero_model_brunette.webp" type="image/webp" />
                  <img
                    src="/images/hero_model_brunette.png"
                    alt="High-Roller Mega Jackpots"
                    loading="lazy"
                    decoding="async"
                    className="h-full w-auto max-h-full object-contain object-bottom drop-shadow-[0_15px_30px_rgba(0,0,0,0.65)]"
                  />
                </picture>
              </div>
            </motion.div>
          ) : (
            /* Slide 3: Mystery Vault Crates */
            <motion.div
              key="mystery-crates"
              custom={dir}
              role="group"
              aria-roledescription="slide"
              initial={reduce ? false : { opacity: 0, x: 40 * dir }}
              animate={{ opacity: 1, x: 0 }}
              exit={reduce ? { opacity: 0 } : { opacity: 0, x: -40 * dir }}
              transition={{ duration: reduce ? 0 : 0.45, ease: "easeOut" }}
              className="relative min-h-[15rem] xs:min-h-[16.5rem] sm:min-h-[19rem] md:min-h-[22rem] lg:min-h-[24rem] overflow-hidden bg-gradient-to-r from-[#171438] via-[#2c1d56] to-[#4338ca] p-4 sm:p-7 md:p-8 lg:p-10 flex flex-col justify-center"
            >
              <SparkleField count={12} className="opacity-70" />

              <div className="relative z-20 w-[60%] sm:w-[58%] lg:w-[62%] max-w-2xl pb-2 sm:pb-4">
                <div className="inline-flex items-center gap-1.5 rounded-full bg-violet-400/20 border border-violet-400/30 px-2.5 py-0.5 text-[9px] sm:text-xs font-black text-violet-300 mb-1.5 sm:mb-2 w-fit">
                  <span>💎 DAILY DIAMOND DROPS</span>
                </div>

                <h2 className="text-base xs:text-lg sm:text-2xl md:text-3xl lg:text-[2.25rem] xl:text-4xl font-black text-white leading-[1.12] tracking-tight drop-shadow-md">
                  Crack Secret{" "}
                  <br className="hidden xs:inline md:hidden" />
                  <span className="bg-gradient-to-r from-violet-300 via-pink-300 to-indigo-200 bg-clip-text text-transparent">
                    Mystery Crates
                  </span>
                </h2>

                <p className="mt-1 text-[11px] xs:text-xs sm:text-sm md:text-base font-extrabold text-violet-200">
                  Open Daily Free Boxes for Instant Credits
                </p>

                <div className="mt-2 sm:mt-3 flex items-center gap-1.5 text-[9px] sm:text-xs font-bold text-white/80">
                  <span className="rounded-md bg-white/10 px-2 py-0.5 border border-white/10">No Deposit Needed</span>
                  <span className="rounded-md bg-white/10 px-2 py-0.5 border border-white/10">Daily Drops</span>
                </div>

                <div className="mt-3 sm:mt-4">
                  <Link
                    href="/bonus-zone"
                    className="inline-flex items-center justify-center rounded-xl sm:rounded-2xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-black px-4 sm:px-6 py-2 sm:py-2.5 text-xs sm:text-sm shadow-lift transition hover:scale-105 active:scale-95"
                  >
                    Open Daily Crate <ArrowUpRight className="h-3.5 w-3.5 ml-1" />
                  </Link>
                </div>
              </div>

              {/* Fast Loading Optimized WebP Cutout */}
              <div className="pointer-events-none absolute bottom-0 right-0 sm:right-2 md:right-4 lg:right-6 xl:right-10 z-10 h-[92%] sm:h-[95%] w-[42%] sm:w-[40%] md:w-[38%] max-w-[320px] lg:max-w-[360px] flex items-end justify-end select-none">
                <picture className="block h-full">
                  <source srcSet="/images/bonus_girl.webp" type="image/webp" />
                  <img
                    src="/images/bonus_girl.png"
                    alt="Crack Secret Mystery Crates"
                    loading="lazy"
                    decoding="async"
                    className="h-full w-auto max-h-full object-contain object-bottom drop-shadow-[0_15px_30px_rgba(0,0,0,0.65)]"
                  />
                </picture>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Navigation arrows for desktop */}
        <button
          onClick={() => go(index - 1, -1)}
          aria-label="Previous slide"
          className="absolute left-3 top-1/2 hidden h-9 w-9 -translate-y-1/2 place-items-center rounded-full bg-black/40 text-white opacity-0 backdrop-blur transition hover:bg-black/60 group-hover:opacity-100 focus-visible:opacity-100 md:grid"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <button
          onClick={() => go(index + 1, 1)}
          aria-label="Next slide"
          className="absolute right-3 top-1/2 hidden h-9 w-9 -translate-y-1/2 place-items-center rounded-full bg-black/40 text-white opacity-0 backdrop-blur transition hover:bg-black/60 group-hover:opacity-100 focus-visible:opacity-100 md:grid"
        >
          <ChevronRight className="h-5 w-5" />
        </button>

        {/* Segmented slider progress indicator bars */}
        <div
          className="absolute inset-x-0 bottom-2.5 z-20 flex justify-start gap-1.5 pl-4 sm:bottom-4 sm:gap-2 sm:pl-7 md:pl-10"
          role="tablist"
          aria-label="Choose slide"
        >
          {Array.from({ length: totalSlides }).map((_, i) => (
            <button
              key={i}
              role="tab"
              aria-selected={i === index}
              aria-label={`Go to slide ${i + 1}`}
              onClick={() => go(i)}
              className="relative h-1 w-6 overflow-hidden rounded-full bg-white/30 sm:w-10 transition-all"
            >
              <span
                className={cn("absolute inset-y-0 left-0 rounded-full bg-white transition-all", i < index && "w-full", i > index && "w-0")}
                style={
                  i === index
                    ? {
                      width: reduce || paused ? "100%" : undefined,
                      animation: reduce || paused ? undefined : `slideprog ${AUTOPLAY_MS}ms linear forwards`,
                    }
                    : undefined
                }
              />
            </button>
          ))}
        </div>
      </div>

      <p className="mt-2 text-center text-[0.7rem] text-slate-400">
        18+ only. Availability depends on your jurisdiction. Play responsibly.
      </p>
      <style>{`@keyframes slideprog { from { width: 0% } to { width: 100% } }`}</style>
    </section>
  );
}
