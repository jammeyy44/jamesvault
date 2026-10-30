"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AuthShell } from "@/components/auth-shell";
import { Notice } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function Verify() {
  const token = useSearchParams().get("token") ?? "";
  const { refresh } = useAuth();
  const [state, setState] = useState<{ tone: "error" | "success"; text: string } | null>(null);

  useEffect(() => {
    if (!token) return;
    api<{ message: string }>("/auth/verify-email", { method: "POST", body: { token } })
      .then((r) => { setState({ tone: "success", text: `${r.message} Your signup bonus (50% on your first cash added to a game) is now unlocked.` }); refresh(); })
      .catch((e) => setState({ tone: "error", text: errorMessage(e) }));
  }, [token, refresh]);

  return (
    <AuthShell title="Confirm your email" footer={<Link className="font-semibold text-primary" href="/dashboard">Go to my account</Link>}>
      {!token ? <Notice tone="error">This confirmation link is incomplete. Request a new one from your account page.</Notice>
        : state ? <div className="space-y-4"><Notice tone={state.tone}>{state.text}</Notice><Button asChild className="w-full"><Link href="/games">Play now</Link></Button></div>
        : <p className="text-sm text-muted">Confirming…</p>}
    </AuthShell>
  );
}

export default function VerifyEmailPage() {
  return <Suspense><Verify /></Suspense>;
}
