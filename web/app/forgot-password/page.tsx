"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthShell, Field } from "@/components/auth-shell";
import { Notice } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [state, setState] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setState(null);
    try {
      const r = await api<{ message: string }>("/auth/forgot", { method: "POST", body: { email: f.get("email") } });
      setState({ tone: "success", text: r.message });
    } catch (err) {
      setState({ tone: "error", text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Reset your password" subtitle="We'll email you a link that works once and expires shortly."
      footer={<Link className="font-semibold text-primary" href="/login">Back to log in</Link>}>
      <form onSubmit={submit} className="space-y-4">
        {state && <Notice tone={state.tone}>{state.text}</Notice>}
        <Field id="email" label="Email" type="email" autoComplete="email" required />
        <Button type="submit" className="w-full" disabled={busy}>{busy ? "Sending…" : "Send reset link"}</Button>
      </form>
    </AuthShell>
  );
}
