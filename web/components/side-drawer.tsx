"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { 
  X, Home, Crown, Users, Headphones, LogOut, Wallet, Info, 
  Gamepad2, ShieldCheck, ChevronRight, Bell, LogIn, UserPlus, Gem 
} from "lucide-react";
import { OPEN_WALLET_EVENT, WALLET_EVENT } from "./wallet-panel";
import { api } from "@/lib/api";
import { Logo } from "./logo";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface SideDrawerProps {
  open: boolean;
  onClose: () => void;
  balance: string | null;
}

export function SideDrawer({ open, onClose, balance }: SideDrawerProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { player, logout, unread } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [bonus, setBonus] = useState<string | null>(null);
  const [rulesOpen, setRulesOpen] = useState(false);
  const [rules, setRules] = useState<{ table: { made: string; wallet: string }[]; note: string; min: string } | null>(null);

  // Real bonus balance from the server, refreshed whenever the wallet changes.
  useEffect(() => {
    if (!player || !open) return;
    let live = true;
    const read = () => api<{ bonus_balance?: string }>("/wallet").then((r) => { if (live) setBonus(r.bonus_balance ?? "0.00"); }).catch(() => {});
    read();
    window.addEventListener(WALLET_EVENT, read);
    return () => { live = false; window.removeEventListener(WALLET_EVENT, read); };
  }, [player, open]);

  const showBonusRules = () => {
    setRulesOpen(true);
    if (!rules) api<{ bonus: { table: { made: string; wallet: string }[]; note: string; min: string } }>("/cashout-rules").then((r) => setRules(r.bonus)).catch(() => {});
  };

  useEffect(() => {
    setMounted(true);
  }, []);

  // Close drawer ONLY when navigation route changes
  useEffect(() => {
    onClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  // Lock background scroll when drawer is open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const doLogout = async () => {
    await logout();
    onClose();
    router.push("/");
  };

  const openWallet = () => {
    onClose();
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(OPEN_WALLET_EVENT));
    }
  };

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  if (!mounted) return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[100] flex">
          {/* Backdrop overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Drawer content sliding in from left */}
          <motion.div
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 300 }}
            className="relative z-10 flex h-full w-[85vw] max-w-[340px] flex-col border-r border-violet-500/30 bg-[#0B0E17] text-white shadow-[0_0_60px_rgba(124,58,237,0.3)] overflow-y-auto"
          >
            {/* Top Bar: Brand Logo + Close Button */}
            <div className="flex items-center justify-between px-5 pt-5 pb-3">
              <Link href="/" onClick={onClose} className="flex items-center gap-2 group">
                <Logo />
              </Link>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close menu"
                className="grid h-9 w-9 place-items-center rounded-xl bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 px-4 space-y-3 pb-6">
              {/* FREE CASH banner pill */}
              <Link
                href="/bonus-zone"
                onClick={onClose}
                className="group relative flex w-full items-center justify-between overflow-hidden rounded-2xl bg-gradient-to-r from-[#7c3aed] via-[#6366f1] to-[#38bdf8] p-3 text-white shadow-[0_6px_20px_rgba(124,58,237,0.4)] transition hover:scale-[1.02] active:scale-[0.98]"
              >
                <div className="flex items-center gap-2.5">
                  <span className="text-2xl drop-shadow">💸</span>
                  <span className="text-sm font-black tracking-wider uppercase">FREE CASH</span>
                </div>
                <ChevronRight className="h-5 w-5 text-white/90 group-hover:translate-x-1 transition" />
              </Link>

              {/* Profile Card (Matching Screenshot 1) */}
              <div className="rounded-2xl border border-white/10 bg-[#121827] p-4 shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="relative grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-[#8b5cf6] to-[#6d28d9] border border-white/25 text-white font-black text-xl shadow-md">
                    <span className="italic font-serif">
                      {player ? player.username.slice(0, 1).toUpperCase() : "L"}
                    </span>
                    <span className="absolute -top-1 -right-1 grid h-4 w-4 place-items-center rounded-full bg-[#121827] border border-white/30 text-[9px] text-sky-400">
                      ✓
                    </span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-base font-black text-white">
                      {player ? (player.email?.split("@")[0] || player.username) : "David Roger"}
                    </p>
                    <p className="truncate text-xs font-semibold text-slate-400">
                      {player ? `@${player.username}` : "nick786"}
                    </p>
                  </div>
                </div>

                {/* Balance & Wager Metrics */}
                <div className="mt-4 space-y-2.5 pt-3 border-t border-white/10">
                  {/* Balance Row */}
                  <div className="flex items-center justify-between rounded-xl bg-[#0B0E17]/60 p-2.5">
                    <div className="flex items-center gap-3">
                      <span className="grid h-8 w-8 place-items-center rounded-full bg-sky-500/20 text-sky-400 font-black text-sm">
                        $
                      </span>
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Balance</p>
                        <p className="text-base font-black text-white tabular-nums">
                          ${balance !== null ? Number(balance).toFixed(2) : "0.00"}
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={openWallet}
                      aria-label="Open wallet"
                      className="grid h-9 w-9 place-items-center rounded-xl bg-sky-400 hover:bg-sky-300 text-slate-950 shadow-[0_4px_12px_rgba(56,189,248,0.4)] transition hover:scale-105 active:scale-95"
                    >
                      <Wallet className="h-4 w-4 fill-current" />
                    </button>
                  </div>

                  {/* Bonus balance row (the (i) explains the bonus cashout rule) */}
                  <div className="flex items-center justify-between rounded-xl bg-[#0B0E17]/60 p-2.5">
                    <div className="flex items-center gap-3">
                      <span className="grid h-8 w-8 place-items-center rounded-full bg-amber-500/20 text-amber-400 font-black text-sm">
                        $
                      </span>
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Bonus balance</p>
                        <p className="text-base font-black text-white tabular-nums" data-testid="drawer-bonus">${bonus !== null ? Number(bonus).toFixed(2) : "0.00"}</p>
                      </div>
                    </div>
                    <button type="button" onClick={showBonusRules} aria-label="Bonus cashout rule" data-testid="drawer-bonus-info"
                      className="grid h-8 w-8 place-items-center rounded-full text-slate-400 transition hover:bg-white/10 hover:text-white">
                      <Info className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Navigation Card */}
              <div className="rounded-2xl border border-white/10 bg-[#121827] p-2 space-y-1">
                <DrawerItem href="/" icon={<Home className="h-5 w-5" />} label="Home" active={isActive("/")} onClick={onClose} />
                <DrawerItem href="/games" icon={<Gamepad2 className="h-5 w-5" />} label="Games" active={isActive("/games")} onClick={onClose} />
                <DrawerItem
                  href="/bonus-zone"
                  icon={<Gem className="h-5 w-5 text-sky-400" />}
                  label="Bonus Zone"
                  badge={<span className="rounded-full bg-sky-500/20 text-sky-300 text-[10px] font-black px-2 py-0.5 border border-sky-400/30">💎 HOT</span>}
                  active={isActive("/bonus-zone")}
                  onClick={onClose}
                />
                <DrawerItem href="/bonus-zone" icon={<Crown className="h-5 w-5 text-amber-400" />} label="VIP Club" active={false} onClick={onClose} />
                <DrawerItem
                  href="/refer"
                  icon={<Users className="h-5 w-5 text-emerald-400" />}
                  label="Invite & Earn"
                  badge={<span className="rounded-full bg-emerald-500/20 text-emerald-300 text-[10px] font-black px-2 py-0.5 border border-emerald-400/30">+$10</span>}
                  active={isActive("/refer")}
                  onClick={onClose}
                />
                <button
                  type="button"
                  onClick={openWallet}
                  className="flex w-full items-center justify-between rounded-xl px-3.5 py-2.5 text-sm font-bold text-slate-300 hover:bg-white/5 hover:text-white transition-all text-left"
                >
                  <div className="flex items-center gap-3">
                    <Wallet className="h-5 w-5 text-cyan-400" />
                    <span>Deposit & Wallet</span>
                  </div>
                  <span className="rounded-full bg-cyan-500/20 text-cyan-300 text-[10px] font-black px-2 py-0.5 border border-cyan-400/30">FAST</span>
                </button>
                {player?.is_admin && (
                  <DrawerItem href="/admin" icon={<ShieldCheck className="h-5 w-5 text-violet-400" />} label="Admin panel" active={isActive("/admin")} onClick={onClose} />
                )}
                <DrawerItem
                  href="/dashboard?tab=notifications"
                  icon={<Bell className="h-5 w-5 text-amber-400" />}
                  label="Notifications"
                  badge={unread > 0 ? <span className="rounded-full bg-rose-500 text-white text-[10px] font-black px-1.5 py-0.5">{unread}</span> : undefined}
                  active={pathname.includes("notifications")}
                  onClick={onClose}
                />
              </div>

              {/* Live Operator Card */}
              <Link
                href="/support"
                onClick={onClose}
                className="flex items-center gap-3 rounded-2xl border border-white/10 bg-[#121827] p-3.5 text-white hover:bg-white/5 transition"
              >
                <div className="grid h-8 w-8 place-items-center rounded-xl bg-violet-500/20 text-violet-400">
                  <Headphones className="h-4 w-4" />
                </div>
                <span className="text-sm font-bold">Live Operator</span>
                <span className="ml-auto inline-flex items-center gap-1 rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-bold text-emerald-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping" />
                  Online
                </span>
              </Link>

              {/* Auth / Logout Button */}
              {player ? (
                <button
                  type="button"
                  onClick={doLogout}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl bg-[#2a1320] hover:bg-[#3d182e] border border-rose-500/20 py-3.5 text-sm font-extrabold text-rose-400 shadow-sm transition active:scale-95"
                >
                  <LogOut className="h-4 w-4" />
                  Logout
                </button>
              ) : (
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <Link
                    href="/login"
                    onClick={onClose}
                    className="flex items-center justify-center gap-1.5 rounded-xl border border-white/10 bg-white/5 py-2.5 text-sm font-bold text-white hover:bg-white/10"
                  >
                    <LogIn className="h-4 w-4" />
                    Log in
                  </Link>
                  <Link
                    href="/register"
                    onClick={onClose}
                    className="flex items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 py-2.5 text-sm font-bold text-white shadow-lift"
                  >
                    <UserPlus className="h-4 w-4" />
                    Register
                  </Link>
                </div>
              )}
            </div>
          </motion.div>

          {rulesOpen && (
            <div className="fixed inset-0 z-[110] grid place-items-center overflow-y-auto bg-black/70 p-4" role="dialog" aria-modal="true" aria-label="Bonus cashout rule" data-testid="drawer-bonus-rules"
              onMouseDown={(e) => { if (e.target === e.currentTarget) setRulesOpen(false); }}>
              <div className="relative my-auto w-full max-w-sm rounded-3xl border border-white/10 bg-[#0B0F1A] p-5 text-white shadow-2xl">
                <button onClick={() => setRulesOpen(false)} aria-label="Close" className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-full border border-white/10 bg-white/5 text-slate-400 transition hover:text-white"><X className="h-4 w-4" /></button>
                <h3 className="pr-10 text-lg font-black">Bonus cashout rule</h3>
                <p className="mt-2 text-sm text-slate-300">Your bonus balance is added to any game instantly from its <b>Add Cash</b> screen, with no approval needed. It can&apos;t be withdrawn directly.</p>
                <div className="mt-3 rounded-2xl border border-[#ffd966]/30 bg-[#ffd966]/10 p-4 text-sm text-[#ffd966]">
                  <p>If a game is funded <b>only by bonus</b>, its balance must reach <b>{rules?.min ?? "$60"}</b> to cash out, and your wallet is credited:</p>
                  <table className="mt-2 w-full text-left">
                    <thead className="text-[11px] font-extrabold uppercase tracking-wider text-[#ffd966]/70"><tr><th className="py-1">Game balance</th><th className="py-1">To wallet</th></tr></thead>
                    <tbody>{(rules?.table ?? []).map((t) => <tr key={t.made} className="border-t border-[#ffd966]/20"><td className="py-1.5 font-bold">{t.made}</td><td className="py-1.5 font-bold text-emerald-300">{t.wallet}</td></tr>)}</tbody>
                  </table>
                  <p className="mt-2 text-xs text-[#ffd966]/80">{rules?.note ?? "The rest of the balance is not carried over."} If you add your own cash to a game, the regular cash table applies instead.</p>
                </div>
                <button onClick={() => setRulesOpen(false)} className="mt-4 h-11 w-full rounded-2xl bg-gradient-to-r from-[#3B82F6] to-[#8B5CF6] text-sm font-black text-white transition hover:brightness-110">Got it</button>
              </div>
            </div>
          )}
        </div>
      )}
    </AnimatePresence>,
    document.body
  );
}

function DrawerItem({
  href,
  icon,
  label,
  badge,
  active,
  onClick,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
  badge?: React.ReactNode;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={cn(
        "flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-bold transition-all",
        active
          ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-[0_4px_15px_rgba(124,58,237,0.35)]"
          : "text-slate-300 hover:bg-white/5 hover:text-white"
      )}
    >
      <span className={active ? "text-white" : "text-slate-400"}>{icon}</span>
      <span>{label}</span>
      {badge && <span className="ml-auto">{badge}</span>}
    </Link>
  );
}
