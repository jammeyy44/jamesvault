"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Lock, LogIn, Mail, Sparkles, User } from "lucide-react";
import { AuthShell, Field } from "@/components/auth-shell";
import { Notice, Spinner } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { afterAuthPath } from "@/lib/utils";

export default function LoginPage() {
  const router = useRouter();
  const { player, loading, refresh } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // If already logged in, go straight to the homepage (or the page they were sent here from)
  useEffect(() => {
    if (!loading && player) {
      router.replace(afterAuthPath());
    }
  }, [player, loading, router]);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ player: { is_admin: boolean } }>("/auth/login", {
        method: "POST",
        body: { identifier: f.get("identifier"), password: f.get("password") },
      });
      await refresh();
      router.push(afterAuthPath());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  // While checking login state, or if already logged in, show sleek status
  if (!loading && player) {
    return (
      <AuthShell title="Already Signed In" subtitle={`Welcome back, @${player.username}`}>
        <div className="py-6 text-center space-y-4">
          <p className="text-sm text-slate-300">You are already signed into your account. Redirecting...</p>
          <div className="flex justify-center gap-3">
            <Button asChild className="bg-gradient-to-r from-[#7c3aed] to-[#38bdf8] text-white font-bold">
              <Link href="/">Go to home</Link>
            </Button>
          </div>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Welcome Back"
      subtitle="Sign in to continue your streak & unlock vault rewards."
      badge="Member Portal"
      footer={
        <div className="space-y-2">
          <p>
            Don&apos;t have an account?{" "}
            <Link className="font-bold text-sky-400 hover:text-sky-300 underline underline-offset-4 transition" href="/register">
              Create an account
            </Link>
          </p>
          <p className="text-xs text-slate-500">
            Sign up takes less than 30 seconds.
          </p>
        </div>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        {error && <Notice tone="error">{error}</Notice>}

        <Field
          id="identifier"
          label="Username or Email"
          placeholder="your_username or email"
          autoComplete="username"
          required
          icon={<User className="h-4 w-4" />}
        />

        <div className="space-y-1">
          <Field
            id="password"
            label="Password"
            type="password"
            placeholder="••••••••••••"
            autoComplete="current-password"
            required
            icon={<Lock className="h-4 w-4" />}
          />
          <div className="flex justify-end pt-1">
            <Link
              href="/forgot-password"
              className="text-xs font-semibold text-slate-400 hover:text-sky-400 transition"
            >
              Forgot password?
            </Link>
          </div>
        </div>

        <button
          type="submit"
          disabled={busy}
          className="group relative mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-[#7c3aed] via-[#6366f1] to-[#38bdf8] px-6 text-sm font-black tracking-wide text-white shadow-[0_4px_25px_rgba(124,58,237,0.4)] transition hover:brightness-110 active:scale-[0.98] disabled:opacity-50"
        >
          {busy ? (
            <>
              <Spinner className="h-4 w-4 text-white" />
              <span>Signing in…</span>
            </>
          ) : (
            <>
              <span>Sign In to Account</span>
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </>
          )}
        </button>
      </form>
    </AuthShell>
  );
}
