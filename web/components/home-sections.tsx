"use client";

import Link from "next/link";
import { ArrowRight, Gift, ShieldCheck, Users } from "lucide-react";
import { GameGrid } from "./game-grid";
import { useApi } from "@/lib/use-api";

export function FourDotsIcon({ className = "h-5 w-5 text-sky-400" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <circle cx="6" cy="6" r="3.2" />
      <circle cx="18" cy="6" r="3.2" />
      <circle cx="6" cy="18" r="3.2" />
      <circle cx="18" cy="18" r="3.2" />
    </svg>
  );
}

export function Eyebrow({ label, title, href, cta, icon }: { label?: string; title: string; href?: string; cta?: string; icon?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        {label && <p className="mb-1 text-xs font-bold uppercase tracking-wider text-sky-400">{label}</p>}
        <div className="flex items-center gap-2.5">
          {icon}
          <h2 className="text-2xl font-black text-white sm:text-3xl tracking-tight">{title}</h2>
        </div>
      </div>
      {href && (
        <Link href={href} className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-bold text-sky-400 hover:text-sky-300 hover:underline">
          {cta} <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      )}
    </div>
  );
}

export function GameCount() {
  const { data } = useApi<{ total: number }>("/games?per_page=1");
  if (!data || data.total < 1) return null;
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-[#131927] px-3 py-1.5 text-xs font-bold text-slate-200 shadow-sm">
      <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" /> {data.total} {data.total === 1 ? "game" : "games"} in the lobby
    </span>
  );
}

export function FeaturedGames() {
  return (
    <section className="container-x mt-8 sm:mt-10">
      <Eyebrow
        icon={<FourDotsIcon className="h-6 w-6 text-sky-400" />}
        title="Our games"
        href="/games"
        cta="Browse all games"
      />
      <GameGrid featuredOnly={false} limit={12} compact />
    </section>
  );
}

const pillars = [
  { icon: ShieldCheck, title: "Protected accounts", text: "Hashed passwords, short-lived single-use reset links and rate-limited sign-in." },
  { icon: Gift, title: "Instant rewards", text: "Boxes, boosts and bonuses are applied the moment you earn them, with every rule shown up front." },
  { icon: Users, title: "Real support", text: "Open a ticket and follow the whole conversation from your dashboard." },
];

export function Pillars() {
  return (
    <section className="container-x mt-16 sm:mt-20">
      <div className="mb-6">
        <p className="text-xs font-bold uppercase tracking-wider text-sky-400">Why players choose us</p>
        <h2 className="text-2xl font-black text-white sm:text-3xl tracking-tight">Built to be trusted</h2>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {pillars.map(({ icon: Icon, title, text }) => (
          <div key={title} className="rounded-2xl border border-white/10 bg-[#131927]/80 p-6 text-white transition hover:-translate-y-1 hover:border-white/20 hover:shadow-lift">
            <span className="mb-4 grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-[#7c3aed] to-[#4f46e5] text-white shadow-md border border-white/20">
              <Icon className="h-5 w-5" />
            </span>
            <h3 className="font-bold text-base text-white">{title}</h3>
            <p className="mt-1.5 text-xs sm:text-sm text-slate-300">{text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
