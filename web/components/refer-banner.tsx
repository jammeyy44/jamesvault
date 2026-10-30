"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, Copy, Gift, UserPlus, Users } from "lucide-react";
import { Diamond } from "./art";
import { Button } from "./ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** "Refer your friends" strip shown between the hero slider and the game lobby. */
export function ReferBanner() {
  const { player, loading } = useAuth();
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);

  const copy = async () => {
    setError(false);
    try {
      const r = await api<{ link: string }>("/referrals/me");
      await navigator.clipboard.writeText(r.link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { setError(true); }
  };

  return (
    <section className="container-x mt-5" aria-labelledby="refer-title">
      <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-r from-[#131927] via-[#1a2238] to-[#131927] px-4 py-2.5 sm:py-3 sm:px-6 text-white shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Left: Compact Icon & Title */}
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-[#7c3aed] to-[#4f46e5] text-white shadow-sm border border-white/20">
              <Users className="h-4 w-4" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h2 id="refer-title" className="text-sm sm:text-base font-extrabold tracking-tight text-white">
                  Refer Friends & Earn Diamonds
                </h2>
                <span className="hidden sm:inline-flex items-center gap-1 rounded-full bg-sky-500/10 px-2 py-0.5 text-[10px] font-bold text-sky-400 border border-sky-400/20">
                  <Gift className="h-3 w-3" /> Lucky Shop
                </span>
              </div>
              <p className="hidden md:block text-xs text-slate-300">
                Share your personal link to unlock bonus boxes and diamonds for verified invites.
              </p>
            </div>
          </div>

          {/* Right: Actions */}
          <div className="flex items-center gap-2 ml-auto sm:ml-0">
            {!loading && player ? (
              <>
                <Button onClick={copy} size="sm" className="h-8 sm:h-9 px-3.5 rounded-xl bg-sky-400 hover:bg-sky-300 text-slate-950 font-black text-xs sm:text-sm shadow-sm transition active:scale-95">
                  {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                  {copied ? "Copied" : "Copy link"}
                </Button>
                <Link href="/refer" className="text-xs font-bold text-sky-400 hover:text-sky-300 hover:underline px-1.5 py-1">
                  My referrals
                </Link>
              </>
            ) : (
              <Button asChild size="sm" className="h-8 sm:h-9 px-3.5 rounded-xl bg-sky-400 hover:bg-sky-300 text-slate-950 font-black text-xs sm:text-sm shadow-sm transition active:scale-95">
                <Link href="/register"><UserPlus className="h-3.5 w-3.5" /> Invite friends</Link>
              </Button>
            )}
          </div>
        </div>
        {error && <p role="alert" className="mt-1 text-xs text-rose-300">We couldn&apos;t copy your link. Open My referrals instead.</p>}
      </div>
    </section>
  );
}
