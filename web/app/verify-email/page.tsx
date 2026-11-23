"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AuthShell } from "@/components/auth-shell";
import { Notice } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function SendLink() {
  const { player, loading } = useAuth();
  const [msg, setMsg] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  if (loading) return <p className="text-sm text-muted">Loading…</p>;
  if (!player) return <div className="space-y-3"><p className="text-sm text-muted">Sign in to verify your email.</p><Button asChild className="w-full"><Link href="/login?return=/verify-email">Sign in</Link></Button></div>;
  if (player.email_verified) return <div className="space-y-3"><Notice tone="success">Your email {player.email} is verified. Your bonuses are unlocked.</Notice><Button asChild className="w-full"><Link href="/games">Play now</Link></Button></div>;
  const send = async () => {
    setBusy(true); setMsg(null);
    try { const r = await api<{ message: string }>("/auth/verify-email/request", { method: "POST" }); setMsg({ tone: "success", text: r.message }); }
    catch (e) { setMsg({ tone: "error", text: errorMessage(e) }); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4">
      <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
        <li><b className="text-ink">50% signup bonus</b> on the first cash you add to any one game</li>
        <li><b className="text-ink">10% bonus</b> on every add, straight into the game</li>
      </ul>
      <p className="text-sm text-muted">We&apos;ll send a confirmation link to <b className="text-ink">{player.email}</b>.</p>
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <Button className="w-full" onClick={send} disabled={busy}>{busy ? "Sending…" : "Send confirmation email"}</Button>
    </div>
  );
}

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
    <AuthShell title="Confirm your email" footer={<Link className="font-semibold text-primary" href="/">Back to the homepage</Link>}>
      {!token ? <SendLink />
        : state ? <div className="space-y-4"><Notice tone={state.tone}>{state.text}</Notice><Button asChild className="w-full"><Link href="/games">Play now</Link></Button></div>
        : <p className="text-sm text-muted">Confirming…</p>}
    </AuthShell>
  );
}

export default function VerifyEmailPage() {
  return <Suspense><Verify /></Suspense>;
}
