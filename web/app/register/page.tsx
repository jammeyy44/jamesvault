"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ArrowRight, Gift, Lock, Mail, Sparkles, User } from "lucide-react";
import { AuthShell, Field } from "@/components/auth-shell";
import { Notice, Spinner } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { player, loading, refresh, config } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const minAge = config?.brand.min_age ?? 18;

  // If already logged in, redirect immediately to dashboard
  useEffect(() => {
    if (!loading && player) {
      router.replace("/dashboard");
    }
  }, [player, loading, router]);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await api("/auth/register", {
        method: "POST",
        body: {
          username: f.get("username"),
          email: f.get("email"),
          password: f.get("password"),
          referral_code: f.get("referral_code") || undefined,
          accept_terms: f.get("accept_terms") === "on",
        },
      });
      await refresh();
      router.push("/dashboard");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  // While checking login state, or if already logged in, show status
  if (!loading && player) {
    return (
      <AuthShell title="Already Registered" subtitle={`Welcome, @${player.username}`}>
        <div className="py-6 text-center space-y-4">
          <p className="text-sm text-slate-300">You already have an active account session. Redirecting...</p>
          <div className="flex justify-center gap-3">
            <Button asChild className="bg-gradient-to-r from-[#7c3aed] to-[#38bdf8] text-white font-bold">
              <Link href="/dashboard">Go to Dashboard</Link>
            </Button>
          </div>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Create VIP Account"
      subtitle="Join thousands of players and claim your first mystery crate."
      badge="Instant Registration"
      footer={
        <div className="space-y-2">
          <p>
            Already registered?{" "}
            <Link className="font-bold text-sky-400 hover:text-sky-300 underline underline-offset-4 transition" href="/login">
              Log in
            </Link>
          </p>
        </div>
      }
    >
      {config && !config.features.registration ? (
        <Notice>Registration is currently closed.</Notice>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {error && <Notice tone="error">{error}</Notice>}

          {/* Promotional Welcome Banner */}
          <div className="flex items-center gap-2.5 rounded-2xl border border-violet-500/30 bg-gradient-to-r from-violet-600/15 via-indigo-600/10 to-sky-500/15 p-3 text-xs text-violet-200">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-violet-500/30 text-amber-300 text-sm">
              🎁
            </span>
            <span className="font-medium">
              <strong className="text-white">Welcome Offer:</strong> Free daily quest diamonds + instant mystery crate unlocked upon email confirmation.
            </span>
          </div>

          <Field
            id="username"
            label="Username"
            placeholder="choose_username"
            autoComplete="username"
            required
            minLength={3}
            maxLength={30}
            hint="3–30 letters, numbers or underscores."
            icon={<User className="h-4 w-4" />}
          />

          <Field
            id="email"
            label="Email Address"
            type="email"
            placeholder="you@example.com"
            autoComplete="email"
            required
            icon={<Mail className="h-4 w-4" />}
          />

          <Field
            id="password"
            label="Password"
            type="password"
            placeholder="••••••••••••"
            autoComplete="new-password"
            required
            minLength={10}
            hint="At least 10 characters, mixing letters & numbers."
            icon={<Lock className="h-4 w-4" />}
          />

          <Field
            id="referral_code"
            label="Referral Code (Optional)"
            placeholder="Enter friend's referral code"
            defaultValue={params.get("ref") ?? ""}
            autoComplete="off"
            icon={<Gift className="h-4 w-4" />}
          />

          <label className="flex items-start gap-3 pt-1 text-xs text-slate-400 select-none cursor-pointer">
            <input
              type="checkbox"
              name="accept_terms"
              required
              className="mt-0.5 h-4 w-4 rounded border-white/20 bg-[#131929] text-violet-600 focus:ring-violet-500 focus:ring-offset-0"
            />
            <span>
              I certify that I am at least {minAge} years of age and agree to the{" "}
              <Link className="font-bold text-sky-400 hover:underline" href="/legal/terms" target="_blank">
                Terms of Service
              </Link>{" "}
              and{" "}
              <Link className="font-bold text-sky-400 hover:underline" href="/legal/privacy" target="_blank">
                Privacy Policy
              </Link>.
            </span>
          </label>

          <button
            type="submit"
            disabled={busy}
            className="group relative mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-[#7c3aed] via-[#6366f1] to-[#38bdf8] px-6 text-sm font-black tracking-wide text-white shadow-[0_4px_25px_rgba(124,58,237,0.4)] transition hover:brightness-110 active:scale-[0.98] disabled:opacity-50"
          >
            {busy ? (
              <>
                <Spinner className="h-4 w-4 text-white" />
                <span>Creating Account…</span>
              </>
            ) : (
              <>
                <span>Create VIP Account</span>
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </>
            )}
          </button>
        </form>
      )}
    </AuthShell>
  );
}

export default function RegisterPage() {
  return (
    <Suspense>
      <RegisterForm />
    </Suspense>
  );
}
