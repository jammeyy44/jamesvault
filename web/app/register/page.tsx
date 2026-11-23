"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ArrowRight, Gift, Lock, Mail, User } from "lucide-react";
import { AuthShell, Field, SubmitButton } from "@/components/auth-shell";
import { Notice } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, errorMessage, type Player } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { afterAuthPath } from "@/lib/utils";

function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { player, loading, signedIn, refresh, config } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const minAge = config?.brand.min_age ?? 18;
  const ref = params.get("ref") ?? "";
  const [showRef, setShowRef] = useState(!!ref);

  useEffect(() => { router.prefetch(afterAuthPath()); }, [router]);
  useEffect(() => {
    if (!loading && player) router.replace(afterAuthPath());
  }, [player, loading, router]);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ player: Player }>("/auth/register", {
        method: "POST",
        body: {
          username: String(f.get("username") || "").trim(),
          email: String(f.get("email") || "").trim(),
          password: f.get("password"),
          referral_code: String(f.get("referral_code") || "").trim() || undefined,
          accept_terms: f.get("accept_terms") === "on",
        },
      });
      signedIn(r.player);           // straight in, no extra request
      router.push(afterAuthPath());
      void refresh();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  if (!loading && player) {
    return (
      <AuthShell title="You're all set" subtitle={`Welcome, @${player.username}. Taking you in…`}>
        <Button asChild className="h-12 w-full text-base font-bold"><Link href="/">Go to the homepage</Link></Button>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      showcase
      title="Create your account"
      subtitle="Free and takes less than a minute."
      footer={<p>Already have an account? <Link className="font-bold text-sky-400 underline-offset-4 transition hover:text-sky-300 hover:underline" href="/login">Sign in</Link></p>}
    >
      {config && !config.features.registration ? (
        <Notice>Registration is currently closed.</Notice>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          {error && <Notice tone="error">{error}</Notice>}

          <div className="flex items-center gap-3 rounded-2xl border border-amber-300/25 bg-gradient-to-r from-amber-300/10 via-fuchsia-500/10 to-transparent p-3.5">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-[#f472d0] to-[#a21caf] text-white"><Gift className="h-5 w-5" /></span>
            <p className="text-sm leading-snug text-slate-200"><b className="text-amber-200">Welcome bonus:</b> verify your email and get <b className="text-white">50% extra</b> on your first game add, then 10% on every add.</p>
          </div>

          <Field id="username" label="Username" placeholder="Pick a username" autoComplete="username" autoCapitalize="none" spellCheck={false}
            required minLength={3} maxLength={30} pattern="[A-Za-z0-9_]{3,30}" title="3–30 letters, numbers or underscores"
            hint="3–30 letters, numbers or underscores." icon={<User className="h-5 w-5" />} />
          <Field id="email" label="Email" type="email" placeholder="you@example.com" autoComplete="email" inputMode="email" autoCapitalize="none"
            spellCheck={false} required icon={<Mail className="h-5 w-5" />} />
          <Field id="password" label="Password" type="password" placeholder="At least 6 characters" autoComplete="new-password" required minLength={6}
            icon={<Lock className="h-5 w-5" />} />

          {showRef ? (
            <Field id="referral_code" label="Referral code" placeholder="Friend's code (optional)" defaultValue={ref} autoComplete="off" autoCapitalize="characters"
              icon={<Gift className="h-5 w-5" />} />
          ) : (
            <button type="button" onClick={() => setShowRef(true)} className="text-sm font-semibold text-sky-400 transition hover:text-sky-300">+ I have a referral code</button>
          )}

          <label className="flex cursor-pointer select-none items-start gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-3.5 text-sm leading-relaxed text-slate-300">
            <input type="checkbox" name="accept_terms" required className="mt-0.5 h-5 w-5 shrink-0 rounded border-white/20 bg-[#131929] accent-violet-500" />
            <span>
              I am at least {minAge} years old and agree to the{" "}
              <Link className="font-semibold text-sky-400 hover:underline" href="/legal/terms" target="_blank">Terms</Link> and{" "}
              <Link className="font-semibold text-sky-400 hover:underline" href="/legal/privacy" target="_blank">Privacy Policy</Link>.
            </span>
          </label>

          <SubmitButton busy={busy} busyLabel="Creating your account">
            Create account <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
          </SubmitButton>
        </form>
      )}
    </AuthShell>
  );
}

export default function RegisterPage() {
  return <Suspense><RegisterForm /></Suspense>;
}
