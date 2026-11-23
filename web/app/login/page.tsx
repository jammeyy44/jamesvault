"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Lock, User } from "lucide-react";
import { AuthShell, Field, SubmitButton } from "@/components/auth-shell";
import { Notice } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, errorMessage, type Player } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { afterAuthPath } from "@/lib/utils";

export default function LoginPage() {
  const router = useRouter();
  const { player, loading, signedIn, refresh } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Warm up the page we will land on, so moving there after signing in is instant
  useEffect(() => { router.prefetch(afterAuthPath()); }, [router]);

  // Already signed in: go straight to the homepage (or the page they were sent here from)
  useEffect(() => {
    if (!loading && player) router.replace(afterAuthPath());
  }, [player, loading, router]);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ player: Player }>("/auth/login", {
        method: "POST",
        body: { identifier: String(f.get("identifier") || "").trim(), password: f.get("password") },
      });
      signedIn(r.player);           // no second request: the answer already says who signed in
      router.push(afterAuthPath());
      void refresh();               // notifications count etc. load in the background
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  if (!loading && player) {
    return (
      <AuthShell title="You're signed in" subtitle={`Welcome back, @${player.username}. Taking you in…`}>
        <Button asChild className="h-12 w-full text-base font-bold"><Link href="/">Go to the homepage</Link></Button>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      showcase
      title="Welcome back"
      subtitle="Sign in to play, add cash and claim your bonuses."
      footer={<p>New here? <Link className="font-bold text-sky-400 underline-offset-4 transition hover:text-sky-300 hover:underline" href="/register">Create a free account</Link></p>}
    >
      <form onSubmit={submit} className="space-y-5" noValidate={false}>
        {error && <Notice tone="error">{error}</Notice>}
        <Field id="identifier" label="Username or email" placeholder="Your username or email" autoComplete="username" autoCapitalize="none"
          spellCheck={false} required icon={<User className="h-5 w-5" />} />
        <Field id="password" label="Password" type="password" placeholder="Your password" autoComplete="current-password" required
          icon={<Lock className="h-5 w-5" />}
          aside={<Link href="/forgot-password" className="text-sm font-semibold text-sky-400 transition hover:text-sky-300">Forgot password?</Link>} />
        <SubmitButton busy={busy} busyLabel="Signing in">
          Sign in <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
        </SubmitButton>
      </form>
    </AuthShell>
  );
}
