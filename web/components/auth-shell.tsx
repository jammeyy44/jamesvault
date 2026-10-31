"use client";

import Link from "next/link";
import { useState } from "react";
import { Eye, EyeOff, Lock, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { Logo } from "./logo";

interface AuthShellProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  badge?: string;
}

export function AuthShell({ title, subtitle, children, footer, badge }: AuthShellProps) {
  return (
    <div className="relative min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-12 overflow-hidden">
      {/* Ambient background glows */}
      <div className="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 h-[420px] w-[620px] rounded-full bg-gradient-to-b from-[#7c3aed]/20 via-[#38bdf8]/10 to-transparent blur-[100px]" />
      <div className="pointer-events-none absolute bottom-10 -right-20 h-72 w-72 rounded-full bg-violet-600/10 blur-[90px]" />

      <div className="relative z-10 w-full max-w-[460px]">
        {/* Brand Logo Header */}
        <div className="mb-7 flex flex-col items-center">
          <Link href="/" className="transition hover:scale-105 active:scale-95" aria-label="Home">
            <Logo size={72} />
          </Link>
        </div>

        {/* Premium Auth Card */}
        <div className="relative rounded-3xl border border-white/10 bg-[#0E1322]/90 backdrop-blur-2xl p-6 sm:p-8 shadow-[0_25px_60px_rgba(0,0,0,0.7),0_0_50px_rgba(124,58,237,0.15)] overflow-hidden">
          {/* Subtle top rainbow border sheen */}
          <div className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-[#7c3aed] to-[#38bdf8]" />

          {/* Optional VIP Badge */}
          {badge && (
            <div className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-violet-400/30 bg-violet-500/10 px-3 py-1 text-[11px] font-extrabold uppercase tracking-wider text-violet-300">
              <Sparkles className="h-3 w-3 text-amber-400" />
              <span>{badge}</span>
            </div>
          )}

          <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">{title}</h1>
          {subtitle && <p className="mt-1.5 text-xs sm:text-sm font-medium text-slate-400">{subtitle}</p>}

          <div className="mt-6">{children}</div>
        </div>

        {/* Footer Navigation */}
        {footer && (
          <div className="mt-5 text-center text-xs sm:text-sm font-medium text-slate-400">
            {footer}
          </div>
        )}

        {/* Trust & Security Signals */}
        <div className="mt-6 flex flex-wrap items-center justify-center gap-4 text-[11px] font-semibold text-slate-500">
          <span className="flex items-center gap-1.5">
            <Lock className="h-3 w-3 text-sky-400" />
            256-Bit SSL
          </span>
          <span className="h-1 w-1 rounded-full bg-slate-700" />
          <span className="flex items-center gap-1.5">
            <Zap className="h-3 w-3 text-amber-400" />
            Instant Cashout
          </span>
          <span className="h-1 w-1 rounded-full bg-slate-700" />
          <span className="flex items-center gap-1.5">
            <ShieldCheck className="h-3 w-3 text-emerald-400" />
            Provably Fair
          </span>
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
}

export function Field({ label, id, hint, type = "text", icon, ...props }: FieldProps) {
  const [showPassword, setShowPassword] = useState(false);
  const isPassword = type === "password";
  const actualType = isPassword ? (showPassword ? "text" : "password") : type;

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-xs font-bold uppercase tracking-wider text-slate-300">
        {label}
      </label>
      <div className="relative flex items-center">
        {icon && (
          <span className="pointer-events-none absolute left-3.5 text-slate-400">
            {icon}
          </span>
        )}
        <input
          id={id}
          name={id}
          type={actualType}
          className={`w-full rounded-xl border border-white/10 bg-[#131929]/90 py-3 text-sm text-white placeholder-slate-500 shadow-inner transition focus:border-violet-500 focus:bg-[#161e31] focus:outline-none focus:ring-2 focus:ring-violet-500/30 ${
            icon ? "pl-10" : "pl-4"
          } ${isPassword ? "pr-11" : "pr-4"}`}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            tabIndex={-1}
            aria-label={showPassword ? "Hide password" : "Show password"}
            className="absolute right-3 grid h-7 w-7 place-items-center rounded-lg text-slate-400 hover:text-white transition"
          >
            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        )}
      </div>
      {hint && <p className="text-[11px] text-slate-400 font-medium">{hint}</p>}
    </div>
  );
}
