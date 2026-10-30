"use client";

/**
 * Original illustration kit for the Bonus Zone: faceted diamonds, coins, treasure chests / gift boxes and the
 * composed hero scenes. Everything is inline SVG (crisp at any size, no external artwork or licences).
 */
import { useId } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";

// ------------------------------------------------------------------ diamond
const GEM_TONES = {
  cyan: ["#bff4ff", "#6fdcff", "#2fb6ff", "#1a7be0", "#0f4fb8"],
  violet: ["#e4d4ff", "#b794ff", "#8b5cf6", "#6d3fe0", "#4527b0"],
  ice: ["#f2fbff", "#cdeeff", "#9fd8f7", "#6fb5e8", "#4d8fc9"],
} as const;

export function Diamond({ size = 48, tone = "cyan", className, glow = true }: { size?: number; tone?: keyof typeof GEM_TONES; className?: string; glow?: boolean }) {
  const c = GEM_TONES[tone];
  return (
    <svg width={size} height={size * 0.9} viewBox="0 0 100 90" className={cn("shrink-0", className)} aria-hidden
      style={glow ? { filter: `drop-shadow(0 0 ${Math.max(6, size / 6)}px ${c[2]}aa)` } : undefined}>
      <polygon points="5,30 28,8 36,30" fill={c[1]} />
      <polygon points="28,8 50,8 36,30" fill={c[0]} />
      <polygon points="50,8 64,30 36,30" fill={c[1]} />
      <polygon points="50,8 72,8 64,30" fill={c[0]} />
      <polygon points="72,8 95,30 64,30" fill={c[2]} />
      <polygon points="5,30 36,30 50,86" fill={c[3]} />
      <polygon points="36,30 64,30 50,86" fill={c[2]} />
      <polygon points="64,30 95,30 50,86" fill={c[4]} />
      <polyline points="5,30 28,8 72,8 95,30 50,86 5,30" fill="none" stroke="#ffffff" strokeOpacity=".55" strokeWidth="1.2" strokeLinejoin="round" />
      <polygon points="36,14 46,14 40,24" fill="#fff" fillOpacity=".7" />
    </svg>
  );
}

export function Coin({ size = 40, className }: { size?: number; className?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 60 60" className={cn("shrink-0", className)} aria-hidden>
      <defs>
        <linearGradient id={`c${id}`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#ffe9a3" /><stop offset=".5" stopColor="#f5b83d" /><stop offset="1" stopColor="#b9770e" /></linearGradient>
      </defs>
      <circle cx="30" cy="30" r="27" fill={`url(#c${id})`} />
      <circle cx="30" cy="30" r="21" fill="none" stroke="#fff3c4" strokeOpacity=".75" strokeWidth="2" />
      <path d="M30 17 41 30 30 43 19 30Z" fill="#fff3c4" fillOpacity=".9" />
      <path d="M30 17 41 30H19Z" fill="#fff" fillOpacity=".7" />
    </svg>
  );
}

// ------------------------------------------------------------------ boxes
export type BoxTone = "gift" | "crystal" | "gold" | "ember" | "emerald";

const CHEST: Record<Exclude<BoxTone, "gift">, { body: [string, string]; lid: [string, string]; band: string; lock: string; glow: string; inner: string }> = {
  gold: { body: ["#c98a1e", "#7a4a0c"], lid: ["#e0a437", "#9a6212"], band: "#ffd966", lock: "#fff0b3", glow: "#ffcc4d", inner: "#ffdf80" },
  crystal: { body: ["#cfeaff", "#7fb8e8"], lid: ["#eaf6ff", "#9fcdf2"], band: "#ffffff", lock: "#6ee7ff", glow: "#8fe3ff", inner: "#c9f4ff" },
  ember: { body: ["#4a2f26", "#241512"], lid: ["#5a3a2f", "#2e1b16"], band: "#ff7a2e", lock: "#ffc266", glow: "#ff8a3d", inner: "#ffb066" },
  emerald: { body: ["#17a673", "#0b5a3f"], lid: ["#25c88d", "#0f7a56"], band: "#f5c84c", lock: "#8ff7c4", glow: "#4df0a8", inner: "#9bffd0" },
};

/** `open`: lid lifts off and light pours out. Used both on the shop cards (closed) and in the opening ceremony. */
export function BoxArt({ tone, open = false, className }: { tone: BoxTone; open?: boolean; className?: string }) {
  const id = useId().replace(/:/g, "");
  const reduce = useReducedMotion();
  const lidMotion = reduce ? { duration: 0 } : { type: "spring" as const, stiffness: 120, damping: 11 };

  if (tone === "gift") {
    return (
      <svg viewBox="0 0 200 180" className={cn("overflow-visible", className)} aria-hidden>
        <defs>
          <linearGradient id={`gb${id}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ff5a5a" /><stop offset="1" stopColor="#b3141f" /></linearGradient>
          <linearGradient id={`gl${id}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#ff7676" /><stop offset="1" stopColor="#d12a35" /></linearGradient>
          <linearGradient id={`gr${id}`} x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#1fa84a" /><stop offset=".5" stopColor="#58e07c" /><stop offset="1" stopColor="#1a9441" /></linearGradient>
        </defs>
        <ellipse cx="100" cy="166" rx="70" ry="9" fill="#000" opacity=".28" />
        <rect x="38" y="84" width="124" height="78" rx="9" fill={`url(#gb${id})`} />
        <rect x="90" y="84" width="20" height="78" fill={`url(#gr${id})`} />
        {open && <ellipse cx="100" cy="86" rx="56" ry="9" fill="#ffe9a3" opacity=".9" />}
        <motion.g animate={open ? { y: -58, rotate: -16, opacity: 1 } : { y: 0, rotate: 0, opacity: 1 }} transition={lidMotion} style={{ originX: 0, originY: 1 }}>
          <rect x="30" y="62" width="140" height="28" rx="9" fill={`url(#gl${id})`} />
          <rect x="90" y="62" width="20" height="28" fill={`url(#gr${id})`} />
          <ellipse cx="76" cy="52" rx="24" ry="15" fill={`url(#gr${id})`} transform="rotate(-24 76 52)" />
          <ellipse cx="124" cy="52" rx="24" ry="15" fill={`url(#gr${id})`} transform="rotate(24 124 52)" />
          <circle cx="100" cy="58" r="11" fill="#2fcf5f" stroke="#a8f5bd" strokeWidth="2" />
          <g fill="#fff" fillOpacity=".92"><circle cx="100" cy="53" r="3.4" /><circle cx="95" cy="58.5" r="3.4" /><circle cx="105" cy="58.5" r="3.4" /><circle cx="100" cy="62" r="3.4" /></g>
        </motion.g>
        <g fill="#2fcf5f" fillOpacity=".55" opacity=".9">{[56, 130].map((x) => <circle key={x} cx={x} cy="124" r="5" />)}</g>
      </svg>
    );
  }

  const c = CHEST[tone];
  return (
    <svg viewBox="0 0 200 180" className={cn("overflow-visible", className)} aria-hidden>
      <defs>
        <linearGradient id={`b${id}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={c.body[0]} /><stop offset="1" stopColor={c.body[1]} /></linearGradient>
        <linearGradient id={`l${id}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={c.lid[0]} /><stop offset="1" stopColor={c.lid[1]} /></linearGradient>
        <radialGradient id={`g${id}`}><stop offset="0" stopColor={c.inner} /><stop offset="1" stopColor={c.glow} stopOpacity="0" /></radialGradient>
      </defs>
      <ellipse cx="100" cy="166" rx="76" ry="9" fill="#000" opacity=".3" />
      {/* body */}
      <rect x="26" y="82" width="148" height="80" rx="11" fill={`url(#b${id})`} />
      <rect x="26" y="130" width="148" height="12" fill={c.band} opacity=".9" />
      <rect x="46" y="82" width="14" height="80" fill={c.band} opacity=".85" />
      <rect x="140" y="82" width="14" height="80" fill={c.band} opacity=".85" />
      <rect x="26" y="82" width="148" height="80" rx="11" fill="none" stroke="#fff" strokeOpacity=".22" strokeWidth="1.5" />
      {tone === "ember" && <path d="M64 96 74 118 66 140M126 100 138 124 130 146" stroke="#ff8a3d" strokeWidth="2.5" fill="none" strokeLinecap="round" opacity=".85" />}
      {/* light + contents when open */}
      {open && (
        <>
          <ellipse cx="100" cy="84" rx="68" ry="13" fill="#10131f" />
          <ellipse cx="100" cy="82" rx="66" ry="46" fill={`url(#g${id})`} opacity=".95" />
          <g transform="translate(0 -4)">
            <polygon points="70,86 80,74 90,86" fill="#6fdcff" /><polygon points="96,88 108,70 120,88" fill="#8b5cf6" /><polygon points="118,86 128,76 136,86" fill="#2fb6ff" />
          </g>
        </>
      )}
      {/* lid */}
      <motion.g animate={open ? { y: -54, rotate: -9, scaleY: 0.72, opacity: 1 } : { y: 0, rotate: 0, scaleY: 1, opacity: 1 }} transition={lidMotion} style={{ originX: 0, originY: 1 }}>
        <path d="M26 86 Q26 40 100 40 Q174 40 174 86 Z" fill={`url(#l${id})`} />
        <path d="M26 86 Q26 40 100 40 Q174 40 174 86 Z" fill="none" stroke="#fff" strokeOpacity=".28" strokeWidth="1.5" />
        <rect x="26" y="78" width="148" height="10" fill={c.band} opacity=".95" />
        <rect x="46" y="48" width="14" height="40" fill={c.band} opacity=".85" />
        <rect x="140" y="48" width="14" height="40" fill={c.band} opacity=".85" />
        <rect x="86" y="70" width="28" height="30" rx="6" fill={c.band} />
        <circle cx="100" cy="84" r="7.5" fill={c.lock} stroke="#fff" strokeOpacity=".8" strokeWidth="1.5" />
        <rect x="97.5" y="84" width="5" height="9" rx="2" fill="#000" opacity=".35" />
      </motion.g>
    </svg>
  );
}

// ------------------------------------------------------------------ scenes
const rays = Array.from({ length: 14 }, (_, i) => i * (360 / 14));

export function SparkleField({ count = 18, className }: { count?: number; className?: string }) {
  const reduce = useReducedMotion();
  const dots = Array.from({ length: count }, (_, i) => ({
    x: (i * 53 + 11) % 100, y: (i * 37 + 7) % 100, s: 2 + ((i * 7) % 4), d: (i % 6) * 0.5,
  }));
  return (
    <div className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)} aria-hidden>
      {dots.map((d, i) => (
        <motion.span key={i} className="absolute rounded-full bg-white" style={{ left: `${d.x}%`, top: `${d.y}%`, width: d.s, height: d.s, boxShadow: "0 0 10px 2px rgba(150,200,255,.8)" }}
          animate={reduce ? { opacity: 0.6 } : { opacity: [0.15, 1, 0.15], scale: [0.8, 1.3, 0.8] }}
          transition={{ duration: 3 + (i % 4), repeat: Infinity, delay: d.d }} />
      ))}
    </div>
  );
}

/** Open treasure chest overflowing with gems, coins, floating tickets and rotating light rays (Bonus Zone hero art). */
export function TreasureScene({ className, tickets = ["FREE PLAY", "BONUSES"] }: { className?: string; tickets?: string[] }) {
  const reduce = useReducedMotion();
  const bob = (delay = 0, amp = 8) => (reduce ? {} : { animate: { y: [0, -amp, 0] }, transition: { duration: 5, repeat: Infinity, ease: "easeInOut" as const, delay } });
  return (
    <div className={cn("relative mx-auto aspect-[1/1] w-full max-w-[34rem]", className)} aria-hidden>
      <motion.div className="absolute inset-[6%] rounded-full opacity-70" style={{ background: "conic-gradient(from 0deg, transparent, rgba(120,140,255,.35), transparent 30%, rgba(80,200,255,.3), transparent 60%, rgba(160,110,255,.35), transparent)" }}
        animate={reduce ? {} : { rotate: 360 }} transition={{ duration: 40, repeat: Infinity, ease: "linear" }} />
      <div className="absolute inset-[10%] rounded-full bg-[radial-gradient(circle,rgba(110,120,255,.55),transparent_65%)] blur-2xl" />
      <svg viewBox="0 0 200 200" className="absolute inset-0 h-full w-full opacity-60">
        {rays.map((a) => <rect key={a} x="99" y="0" width="2" height="100" fill="url(#ray)" transform={`rotate(${a} 100 100)`} />)}
        <defs><linearGradient id="ray" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#9fb4ff" stopOpacity="0" /><stop offset=".6" stopColor="#9fb4ff" stopOpacity=".5" /><stop offset="1" stopColor="#fff" stopOpacity="0" /></linearGradient></defs>
      </svg>
      <SparkleField count={22} />

      <motion.div {...bob(0.2, 10)} className="absolute left-[4%] top-[24%] -rotate-6"><Diamond size={92} tone="violet" /></motion.div>
      <motion.div {...bob(1.1, 8)} className="absolute right-[8%] top-[10%] rotate-12"><Diamond size={64} tone="cyan" /></motion.div>
      <motion.div {...bob(0.6, 6)} className="absolute right-[26%] top-[2%]"><Coin size={70} /></motion.div>
      <motion.div {...bob(1.6, 7)} className="absolute left-[34%] top-[30%] opacity-80"><Diamond size={36} tone="ice" /></motion.div>

      {tickets.map((t, i) => (
        <motion.div key={t} {...bob(0.4 + i * 0.7, 9)}
          className={cn("absolute hidden rounded-lg border px-4 py-2 text-center text-[0.8rem] font-black leading-tight tracking-wide text-white shadow-lift sm:block",
            i === 0 ? "left-[24%] top-[12%] -rotate-12 border-violet/60 bg-gradient-to-br from-[#5b2fd8] to-[#2b1a8a]" : "right-[6%] top-[38%] rotate-6 border-electric/60 bg-gradient-to-br from-[#1b6fe0] to-[#16308f]")}
          style={{ boxShadow: "0 0 24px rgba(110,130,255,.55)" }}>{t}</motion.div>
      ))}

      <div className="absolute bottom-[4%] left-1/2 w-[62%] -translate-x-[58%]"><BoxArt tone="gold" open className="w-full drop-shadow-[0_18px_30px_rgba(0,0,0,.55)]" /></div>
      <motion.div {...bob(0.9, 5)} className="absolute bottom-[26%] left-[34%]"><Diamond size={54} tone="cyan" /></motion.div>
      <div className="absolute bottom-[6%] left-[2%] flex flex-col items-center gap-0.5">{[0, 1, 2].map((i) => <Coin key={i} size={46} className={i === 1 ? "translate-x-2" : ""} />)}</div>
      <div className="absolute bottom-[8%] right-[4%]"><Coin size={64} /></div>
    </div>
  );
}
