"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Bell, Check, ChevronDown, LayoutDashboard, LifeBuoy, LogOut, Menu, Shield, ShieldCheck, Wallet, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Logo } from "./logo";
import { OPEN_WALLET_EVENT, WALLET_EVENT, WalletDrawer } from "./wallet-panel";
import { SideDrawer } from "./side-drawer";
import { api } from "@/lib/api";
import { Button } from "./ui/button";
import { navLinks } from "@/lib/brand";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { player, loading, logout, unread, config } = useAuth();
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const [walletOpen, setWalletOpen] = useState(false);
  const [balance, setBalance] = useState<string | null>(null);
  const reduce = useReducedMotion();
  const [tipSeen, setTipSeen] = useState(true);  // true until we know, so the tip never flashes for someone who dismissed it

  // First-visit hint pointing at the wallet. Remembered per browser; storage may be blocked, so it just shows again then.
  useEffect(() => {
    try { setTipSeen(localStorage.getItem("jv-wallet-tip") === "1"); } catch { setTipSeen(false); }
  }, []);
  const dismissTip = () => { setTipSeen(true); try { localStorage.setItem("jv-wallet-tip", "1"); } catch { /* ignore */ } };
  const openWallet = () => { dismissTip(); setWalletOpen(true); };

  // Header balance chip: always read fresh from the server, refreshed whenever the wallet changes.
  useEffect(() => {
    if (!player) { setBalance(null); return; }
    let live = true;
    // The light balance endpoint (no payment-provider call) is read straight away, every few seconds while the tab is visible,
    // whenever the wallet changes, and the moment the player comes back to the tab (e.g. after paying on the provider's page).
    const read = () => { if (document.hidden) return; api<{ enabled: boolean; balance: string | null }>("/wallet/balance").then((r) => { if (live) setBalance(r.enabled ? r.balance : null); }).catch(() => {}); };
    read();
    const timer = setInterval(read, 4000);
    window.addEventListener(WALLET_EVENT, read);
    window.addEventListener("focus", read);
    document.addEventListener("visibilitychange", read);
    return () => { live = false; clearInterval(timer); window.removeEventListener(WALLET_EVENT, read); window.removeEventListener("focus", read); document.removeEventListener("visibilitychange", read); };
  }, [player]);

  useEffect(() => {
    const open = () => { dismissTip(); setWalletOpen(true); };
    window.addEventListener(OPEN_WALLET_EVENT, open);
    return () => window.removeEventListener(OPEN_WALLET_EVENT, open);
  }, []);

  useEffect(() => { setOpen(false); setMenu(false); }, [pathname]);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenu(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  const doLogout = async () => { await logout(); router.push("/"); };

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-[#0B0E17]/90 backdrop-blur-md">
      <div className="container-x flex h-16 items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link href="/" aria-label="Home"><Logo /></Link>
          <Link href="/bonus-zone"
            className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-[#7c3aed] to-[#4f46e5] px-3.5 py-1 text-xs font-black text-white shadow-[0_4px_16px_rgba(124,58,237,0.45)] border border-white/20 transition hover:scale-105 active:scale-95">
            💸 FREE CASH →
          </Link>
        </div>

        <nav aria-label="Main" className="hidden items-center gap-1.5 lg:flex">
          {navLinks.map((l) => (
            <Link key={l.href} href={l.href}
              className={cn("rounded-full px-4 py-2 text-sm font-bold transition-all",
                isActive(l.href) ? "bg-gradient-to-r from-[#7c3aed] to-[#4f46e5] text-white shadow-[0_4px_18px_rgba(124,58,237,0.45)]" : "text-slate-300 hover:bg-white/5 hover:text-white")}>
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          {loading ? (
            <div className="h-9 w-20 sm:w-28 animate-pulse rounded-full bg-white/5" />
          ) : player ? (
            <>
              {/* 1. Wallet: balance + one big, obvious button (opens Add Cash / Cashout / History) */}
              <div className="relative">
                <button
                  type="button"
                  onClick={openWallet}
                  aria-label="Open wallet"
                  title="Add cash, cash out, history"
                  className="group flex h-11 cursor-pointer items-center gap-2.5 rounded-2xl border border-white/[0.07] bg-[#161C2C] py-1 pl-2.5 pr-1 transition hover:border-white/15 hover:bg-[#1A2236] active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300"
                >
                  <span className="grid h-7 w-7 place-items-center rounded-full bg-[#1F3350] text-[13px] font-bold text-sky-300">$</span>
                  <span className="min-w-[2.6rem] text-[15px] font-semibold tabular-nums text-slate-100" data-testid="header-balance">
                    {balance !== null ? Number(balance).toFixed(2) : "0.00"}
                  </span>
                  <span className="relative grid h-9 w-10 place-items-center rounded-xl bg-[#58B2F7] text-[#0B1B33] transition group-hover:bg-[#6FBFFA]">
                    {!tipSeen && !reduce && <span className="absolute inset-0 -z-10 animate-ping rounded-xl bg-sky-400/40" aria-hidden />}
                    <Wallet className="h-[19px] w-[19px]" strokeWidth={1.9} />
                  </span>
                </button>

                <AnimatePresence>
                  {!tipSeen && balance !== null && (
                    <motion.div
                      role="dialog" aria-label="Wallet tip" data-testid="wallet-tip"
                      initial={reduce ? false : { opacity: 0, y: -8, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.25 }}
                      className="absolute right-0 top-[calc(100%+0.85rem)] z-50 w-64 max-w-[calc(100vw-2rem)] rounded-2xl border border-indigo-300/30 bg-gradient-to-br from-[#2a2466] to-[#1b1748] p-4 shadow-[0_18px_40px_rgba(0,0,0,0.55)]"
                    >
                      <span className="absolute -top-1.5 right-6 h-3 w-3 rotate-45 border-l border-t border-indigo-300/30 bg-[#2a2466]" aria-hidden />
                      <button onClick={dismissTip} aria-label="Dismiss tip" className="absolute right-2.5 top-2.5 rounded-full p-1 text-white/70 transition hover:bg-white/10 hover:text-white"><X className="h-4 w-4" /></button>
                      <p className="text-[11px] font-black uppercase tracking-[0.2em] text-amber-300">Tap here</p>
                      <p className="mt-1 text-base font-extrabold leading-snug text-white">Add &amp; cashout credits</p>
                      <p className="mt-1 text-sm leading-snug text-slate-300">Tap on here to add and cashout your credits.</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* 2. Notification bell */}
              <Link
                href="/dashboard?tab=notifications"
                aria-label="Notifications"
                className="relative grid h-11 w-11 place-items-center rounded-2xl border border-white/[0.07] bg-[#161C2C] text-slate-400 transition hover:border-white/15 hover:text-slate-200"
              >
                <Bell className="h-[18px] w-[18px]" strokeWidth={1.8} />
                {unread > 0 && (
                  <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-sky-400 ring-2 ring-[#161C2C]" />
                )}
              </Link>

              {/* 3. User profile avatar - opens the side drawer */}
              <button
                onClick={() => setOpen(true)}
                aria-label="Open profile menu"
                className="relative grid h-11 w-11 place-items-center rounded-full border-2 border-white/15 bg-[#161C2C] p-[3px] transition hover:border-white/30 active:scale-95"
              >
                <span className="grid h-full w-full place-items-center rounded-full bg-gradient-to-br from-[#8B5CF6] to-[#6D28D9] text-[15px] font-bold uppercase text-white">
                  {player.username.slice(0, 1)}
                </span>
                <span className="absolute -right-0.5 -top-0.5 grid h-[18px] w-[18px] place-items-center rounded-full border border-white/20 bg-[#2A3042] text-slate-200" aria-hidden>
                  <Check className="h-2.5 w-2.5" strokeWidth={3.5} />
                </span>
              </button>
            </>
          ) : (
            /* When user hasn't logged in: ONLY show Sign In and Sign Up */
            <div className="flex items-center gap-1.5 sm:gap-2">
              <Button asChild variant="ghost" size="sm" className="text-slate-200 hover:text-white hover:bg-white/10 font-bold px-3 sm:px-4">
                <Link href="/login">Sign In</Link>
              </Button>
              {config?.features.registration !== false && (
                <Button asChild size="sm" className="bg-gradient-to-r from-[#7c3aed] via-[#6366f1] to-[#38bdf8] text-white font-extrabold shadow-[0_4px_15px_rgba(124,58,237,0.5)] hover:scale-105 active:scale-95 transition px-3 sm:px-5">
                  <Link href="/register">Sign Up</Link>
                </Button>
              )}
            </div>
          )}
        </div>
      </div>

      <WalletDrawer open={walletOpen} onClose={() => setWalletOpen(false)} />
      <SideDrawer open={open} onClose={() => setOpen(false)} balance={balance} />
    </header>
  );
}
