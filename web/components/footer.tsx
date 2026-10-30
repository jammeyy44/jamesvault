"use client";

import Link from "next/link";
import { Logo } from "./logo";
import { brand, navLinks } from "@/lib/brand";
import { OPEN_WALLET_EVENT } from "./wallet-panel";
import { SignupBonusBanner } from "./signup-bonus-banner";

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
        {/* Navigation & brand links */}
        <div className="grid gap-10 md:grid-cols-[1.4fr_1fr_1fr] pb-10">
          <div>
            <Logo />
            <p className="mt-4 max-w-sm text-sm text-slate-400">{brand.description}</p>
          </div>
          <nav aria-label="Explore">
            <h2 className="mb-3 text-sm font-bold text-white">Explore</h2>
            <ul className="space-y-2 text-sm text-slate-400">
              {navLinks.map((l) => (
                <li key={l.href}>
                  <Link className="hover:text-sky-400 transition" href={l.href}>
                    {l.label}
                  </Link>
                </li>
              ))}
              <li>
                <Link className="hover:text-sky-400 transition" href="/support">
                  Help &amp; Support
                </Link>
              </li>
            </ul>
          </nav>
          <nav aria-label="Legal">
            <h2 className="mb-3 text-sm font-bold text-white">Legal &amp; safety</h2>
            <ul className="space-y-2 text-sm text-slate-400">
              <li>
                <Link className="hover:text-sky-400 transition" href="/legal/terms">
                  Terms &amp; Conditions
                </Link>
              </li>
              <li>
                <Link className="hover:text-sky-400 transition" href="/legal/privacy">
                  Privacy Policy
                </Link>
              </li>
              <li>
                <Link className="hover:text-sky-400 transition" href="/cashout-rules">
                  Cashout Rules
                </Link>
              </li>
              <li>
                <Link className="hover:text-sky-400 transition" href="/legal/responsible-gaming">
                  Responsible Gaming
                </Link>
              </li>
            </ul>
          </nav>
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
