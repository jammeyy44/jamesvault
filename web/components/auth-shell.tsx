"use client";

import Link from "next/link";
import { useState } from "react";
import { BadgeCheck, Eye, EyeOff, Gift, Lock, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { Logo } from "./logo";

interface AuthShellProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  badge?: string;
  /** Show the brand panel beside the form on large screens (sign in / sign up). */
  showcase?: boolean;
}

const PERKS = [
  { icon: Gift, title: "50% signup bonus", text: "On your first cash add to any game, after you verify your email." },
  { icon: Zap, title: "Instant game loads", text: "Add cash to Juwa, Game Vault and more in seconds, no waiting." },
  { icon: BadgeCheck, title: "10% on every add", text: "A regular bonus straight into your game, every time." },
];

/** The frame for every account page: a calm, readable form card, with an optional brand panel on wide screens. */
export function AuthShell({ title, subtitle, children, footer, badge, showcase = false }: AuthShellProps) {
  return (
    <div className="relative flex min-h-[calc(100vh-4rem)] items-center justify-center overflow-hidden px-4 py-10 sm:py-14">
      <div className="pointer-events-none absolute -top-32 left-1/2 h-[460px] w-[760px] -translate-x-1/2 rounded-full bg-gradient-to-b from-[#7c3aed]/20 via-[#38bdf8]/10 to-transparent blur-[110px]" aria-hidden />
      <div className="pointer-events-none absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-fuchsia-600/10 blur-[100px]" aria-hidden />

      <div className={`relative z-10 grid w-full items-stretch gap-6 ${showcase ? "max-w-5xl lg:grid-cols-[1fr_440px]" : "max-w-[440px]"}`}>
        {showcase && (
          <aside className="relative hidden overflow-hidden rounded-[28px] border border-white/10 bg-gradient-to-br from-[#2a1559] via-[#16183b] to-[#0b1124] p-10 lg:flex lg:flex-col lg:justify-between">
            <div className="pointer-events-none absolute -left-16 -top-20 h-72 w-72 rounded-full bg-fuchsia-500/25 blur-3xl" aria-hidden />
            <div className="pointer-events-none absolute -bottom-24 right-0 h-72 w-72 rounded-full bg-sky-400/20 blur-3xl" aria-hidden />
            <div className="relative">
              <Link href="/" aria-label="Home" className="inline-block transition hover:scale-105"><Logo size={84} /></Link>
              <h2 className="mt-8 text-[2.1rem] font-black leading-[1.12] tracking-tight text-white">
                Your next winning moment <span className="bg-gradient-to-r from-amber-200 via-yellow-200 to-amber-400 bg-clip-text text-transparent">starts here.</span>
              </h2>
              <p className="mt-3 max-w-md text-[15px] leading-relaxed text-slate-300">One account for every game, a wallet that loads in seconds, and bonuses that go straight into your game.</p>
            </div>
            <ul className="relative mt-10 space-y-4">
              {PERKS.map(({ icon: Icon, title: t, text }) => (
                <li key={t} className="flex items-start gap-4 rounded-2xl border border-white/10 bg-white/[0.05] p-4 backdrop-blur">
                  <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-[#e879f9] to-[#6366f1] text-white shadow-[0_8px_20px_rgba(168,85,247,0.35)]"><Icon className="h-5 w-5" /></span>
                  <span><span className="block text-[15px] font-bold text-white">{t}</span><span className="mt-0.5 block text-sm leading-snug text-slate-300">{text}</span></span>
                </li>
              ))}
            </ul>
          </aside>
        )}

        <div className="flex flex-col justify-center">
          <div className={`mb-6 flex justify-center ${showcase ? "lg:hidden" : ""}`}>
            <Link href="/" className="transition hover:scale-105 active:scale-95" aria-label="Home"><Logo size={76} /></Link>
          </div>

          <div className="relative overflow-hidden rounded-[28px] border border-white/10 bg-[#0d1220]/95 p-6 shadow-[0_30px_70px_rgba(0,0,0,0.65),0_0_60px_rgba(124,58,237,0.12)] backdrop-blur-2xl sm:p-8">
            <div className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-[#e879f9] via-[#7c3aed] to-[#38bdf8]" aria-hidden />
            {badge && (
              <div className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-violet-400/30 bg-violet-500/10 px-3 py-1 text-xs font-bold text-violet-200">
                <Sparkles className="h-3.5 w-3.5 text-amber-300" />{badge}
              </div>
            )}
            <h1 className="text-[1.75rem] font-black leading-tight tracking-tight text-white sm:text-[2rem]">{title}</h1>
            {subtitle && <p className="mt-2 text-[15px] leading-relaxed text-slate-400">{subtitle}</p>}
            <div className="mt-7">{children}</div>
          </div>

          {footer && <div className="mt-5 text-center text-[15px] text-slate-400">{footer}</div>}

          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs font-semibold text-slate-500">
            <span className="flex items-center gap-1.5"><Lock className="h-3.5 w-3.5 text-sky-400" />Encrypted connection</span>
            <span className="flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />Secure payments</span>
            <span className="flex items-center gap-1.5"><BadgeCheck className="h-3.5 w-3.5 text-amber-300" />18+ only</span>
          </div>
        </div>
      </div>
    </div>
  );
}

interface FieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  id: string;
  hint?: string;
  icon?: React.ReactNode;
  /** Something small on the right of the label row, e.g. a "Forgot password?" link. */
  aside?: React.ReactNode;
}

/** A large, easy-to-tap input. 16px text so phones do not zoom in while typing. */
export function Field({ label, id, hint, type = "text", icon, aside, ...props }: FieldProps) {
  const [showPassword, setShowPassword] = useState(false);
  const isPassword = type === "password";
  const actualType = isPassword ? (showPassword ? "text" : "password") : type;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={id} className="text-sm font-semibold text-slate-200">{label}</label>
        {aside}
      </div>
      <div className="group relative flex items-center">
        {icon && <span className="pointer-events-none absolute left-4 text-slate-500 transition group-focus-within:text-violet-300">{icon}</span>}
        <input
          id={id}
          name={id}
          type={actualType}
          className={`h-[52px] w-full rounded-2xl border border-white/10 bg-[#141a2b] text-base text-white placeholder:text-slate-500 shadow-inner transition hover:border-white/20 focus:border-violet-400 focus:bg-[#161e33] focus:outline-none focus:ring-4 focus:ring-violet-500/20 ${
            icon ? "pl-12" : "pl-4"
          } ${isPassword ? "pr-12" : "pr-4"}`}
          {...props}
        />
        {isPassword && (
          <button type="button" onClick={() => setShowPassword(!showPassword)} tabIndex={-1} aria-label={showPassword ? "Hide password" : "Show password"}
            className="absolute right-2.5 grid h-9 w-9 place-items-center rounded-xl text-slate-400 transition hover:bg-white/10 hover:text-white">
            {showPassword ? <EyeOff className="h-[18px] w-[18px]" /> : <Eye className="h-[18px] w-[18px]" />}
          </button>
        )}
      </div>
      {hint && <p className="text-[13px] leading-snug text-slate-400">{hint}</p>}
    </div>
  );
}

/** The big gradient submit button used on the account pages. */
export function SubmitButton({ busy, busyLabel, children }: { busy: boolean; busyLabel: string; children: React.ReactNode }) {
  return (
    <button type="submit" disabled={busy}
      className={`group relative flex h-[54px] w-full items-center justify-center gap-2 overflow-hidden rounded-2xl bg-gradient-to-r from-[#7c3aed] via-[#6366f1] to-[#38bdf8] px-6 text-base font-bold text-white shadow-[0_10px_30px_rgba(124,58,237,0.4)] transition hover:brightness-110 active:scale-[0.98] disabled:cursor-wait ${busy ? "btn-processing" : ""}`}>
      {busy ? <span className="inline-flex items-center">{busyLabel}<span className="proc-dots" aria-hidden><i /><i /><i /></span></span> : children}
    </button>
  );
}
