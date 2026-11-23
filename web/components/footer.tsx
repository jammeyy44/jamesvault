"use client";

import Link from "next/link";
import { ChevronRight, ShieldCheck, Zap } from "lucide-react";
import { Logo } from "./logo";
import { brand, navLinks } from "@/lib/brand";
import { OPEN_WALLET_EVENT } from "./wallet-panel";
import { SignupBonusBanner } from "./signup-bonus-banner";

/** One footer column: a small heading with an accent line and quiet links that brighten (with a sliding chevron) on hover. */
function FooterCol({ title, links }: { title: string; links: { href: string; label: string }[] }) {
  return (
    <nav aria-label={title}>
      <h2 className="text-xs font-bold uppercase tracking-[0.14em] text-white">{title}</h2>
      <span className="mt-2 block h-0.5 w-8 rounded-full bg-gradient-to-r from-[#8B5CF6] to-[#38BDF8]" aria-hidden />
      <ul className="mt-4 space-y-2.5">
        {links.map((l) => (
          <li key={l.href}>
            <Link href={l.href} className="group relative inline-flex items-center text-sm text-slate-400 transition hover:translate-x-1 hover:text-white">
              <ChevronRight className="absolute -left-4 h-3.5 w-3.5 text-sky-400 opacity-0 transition group-hover:opacity-100" aria-hidden />
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function Footer() {
  const openDeposit = () => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(OPEN_WALLET_EVENT));
    }
  };

  return (
    <footer className="mt-20 border-t border-white/10 bg-[#080B12] text-slate-300">
      <div className="container-x py-12">
        <SignupBonusBanner />
        {/* Brand + two link columns (side by side even on phones, so they stay short) */}
        <div className="mb-8 grid grid-cols-2 gap-x-6 gap-y-8 border-b border-white/10 pb-8 md:grid-cols-[1.6fr_1fr_1fr] md:gap-10">
          <div className="col-span-2 md:col-span-1">
            <Logo size={60} />
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-slate-400">{brand.description}</p>
            <div className="mt-4 flex flex-wrap gap-2 text-[11px] font-semibold text-slate-400">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1"><ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />Secure payments</span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1"><Zap className="h-3.5 w-3.5 text-amber-300" />Instant game loads</span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1">18+ only</span>
            </div>
          </div>
          <FooterCol title="Explore" links={[...navLinks.map((l) => ({ href: l.href, label: l.label })), { href: "/support", label: "Help & Support" }]} />
          <FooterCol title="Legal & safety" links={[
            { href: "/legal/terms", label: "Terms & Conditions" },
            { href: "/legal/privacy", label: "Privacy Policy" },
            { href: "/cashout-rules", label: "Cashout Rules" },
            { href: "/legal/responsible-gaming", label: "Responsible Gaming" },
          ]} />
        </div>

        {/* Regulatory, Licensing & Payment Methods Card (Matches Reference Screenshot) */}
        <div className="rounded-[1.75rem] sm:rounded-3xl border border-white/10 bg-[#0F1424] p-5 sm:p-7 shadow-lift">
          {/* Top: 18+ Badge + Legal Disclaimer */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 sm:gap-6">
            <div className="grid h-14 w-14 sm:h-16 sm:w-16 shrink-0 place-items-center rounded-full border-2 border-white/30 text-white/90">
              <span className="text-lg sm:text-xl font-bold tracking-tight">18+</span>
            </div>
            <p className="text-xs sm:text-[13px] leading-relaxed text-slate-400">
              stakesweep.net owned and operated by StakeSweep Gaming Ltd, registered in accordance with the laws of the Autonomous
              Island of Anjouan, registration number: 15734, registered address: Hamchako, Mutsamudu, Autonomous Island
              of Anjouan, Union of Comoros. stakesweep.net licensed and regulated by the Government of Cyprus.
            </p>
          </div>

          {/* Payment Method Badges Row - Clicking opens the wallet deposit section directly */}
          <div className="mt-6 pt-5 border-t border-white/10">
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-3">
              Accepted Deposit &amp; Payout Methods (Click to Deposit)
            </p>
            <div className="flex flex-wrap items-center gap-2.5 sm:gap-3">
              {/* Cash App */}
              <button
                type="button"
                onClick={openDeposit}
                title="Deposit with Cash App"
                aria-label="Deposit with Cash App"
                className="grid h-11 w-14 sm:h-12 sm:w-16 place-items-center rounded-2xl bg-[#00D632] text-white font-black text-2xl shadow-md transition hover:scale-105 active:scale-95"
              >
                <span>$</span>
              </button>

              {/* VISA */}
              <button
                type="button"
                onClick={openDeposit}
                title="Deposit with VISA"
                aria-label="Deposit with VISA"
                className="grid h-11 w-14 sm:h-12 sm:w-16 place-items-center rounded-2xl bg-[#00579F] text-white font-black italic tracking-wide text-sm sm:text-base shadow-md transition hover:scale-105 active:scale-95"
              >
                <span>VISA</span>
              </button>

              {/* MasterCard */}
              <button
                type="button"
                onClick={openDeposit}
                title="Deposit with MasterCard"
                aria-label="Deposit with MasterCard"
                className="grid h-11 w-14 sm:h-12 sm:w-16 place-items-center rounded-2xl bg-white shadow-md transition hover:scale-105 active:scale-95"
              >
                <div className="flex -space-x-2.5 items-center">
                  <div className="h-6 w-6 rounded-full bg-[#EB001B]" />
                  <div className="h-6 w-6 rounded-full bg-[#F79E1B]/95" />
                </div>
              </button>

              {/* Bitcoin */}
              <button
                type="button"
                onClick={openDeposit}
                title="Deposit with Bitcoin"
                aria-label="Deposit with Bitcoin"
                className="grid h-11 w-14 sm:h-12 sm:w-16 place-items-center rounded-2xl bg-[#F7931A] text-white font-black text-xl sm:text-2xl shadow-md transition hover:scale-105 active:scale-95"
              >
                <span>₿</span>
              </button>

              {/* Ethereum */}
              <button
                type="button"
                onClick={openDeposit}
                title="Deposit with Ethereum"
                aria-label="Deposit with Ethereum"
                className="grid h-11 w-14 sm:h-12 sm:w-16 place-items-center rounded-2xl bg-[#627EEA] text-white font-black shadow-md transition hover:scale-105 active:scale-95"
              >
                <svg className="h-6 w-6 fill-white" viewBox="0 0 32 32">
                  <path d="M16 2.5l-9.8 14.5L16 22.8l9.8-5.8z" opacity="0.8" />
                  <path d="M16 2.5v20.3l9.8-5.8z" />
                  <path d="M16 24.5l-9.8-5.7L16 29.5l9.8-10.7z" opacity="0.8" />
                  <path d="M16 24.5v5l9.8-10.7z" />
                </svg>
              </button>

              {/* Litecoin */}
              <button
                type="button"
                onClick={openDeposit}
                title="Deposit with Litecoin"
                aria-label="Deposit with Litecoin"
                className="grid h-11 w-14 sm:h-12 sm:w-16 place-items-center rounded-2xl bg-[#C8C8C8] text-slate-800 font-black italic text-xl shadow-md transition hover:scale-105 active:scale-95"
              >
                <span>Ł</span>
              </button>

              {/* Tether USDT */}
              <button
                type="button"
                onClick={openDeposit}
                title="Deposit with Tether (USDT)"
                aria-label="Deposit with Tether"
                className="grid h-11 w-14 sm:h-12 sm:w-16 place-items-center rounded-2xl bg-[#26A17B] text-white font-black text-xl shadow-md transition hover:scale-105 active:scale-95"
              >
                <span>₮</span>
              </button>

              {/* USD Coin */}
              <button
                type="button"
                onClick={openDeposit}
                title="Deposit with USD Coin"
                aria-label="Deposit with USD Coin"
                className="grid h-11 w-14 sm:h-12 sm:w-16 place-items-center rounded-2xl bg-[#2775CA] text-white font-black text-sm sm:text-base shadow-md transition hover:scale-105 active:scale-95"
              >
                <span>($)</span>
              </button>

              {/* +21 badge */}
              <button
                type="button"
                onClick={openDeposit}
                title="View more payment methods"
                aria-label="View more payment methods"
                className="grid h-11 w-14 sm:h-12 sm:w-16 place-items-center rounded-2xl bg-[#1C2337] border border-white/10 text-white font-black text-sm shadow-md transition hover:scale-105 active:scale-95"
              >
                <span>+21</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="border-t border-white/10">
        <p className="container-x py-5 text-xs text-slate-400">
          © {new Date().getFullYear()} {brand.name}. For adults only; availability depends on your jurisdiction.
          Play responsibly.
        </p>
      </div>
    </footer>
  );
}
