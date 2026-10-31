"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthShell, Field } from "@/components/auth-shell";
import { Notice } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";

function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const [state, setState] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    if (f.get("password") !== f.get("confirm")) {
      setState({ tone: "error", text: "Passwords do not match." });
      return;
    }
    setBusy(true);
    setState(null);
    try {
      const r = await api<{ message: string }>("/auth/reset", { method: "POST", body: { token, password: f.get("password") } });
      setState({ tone: "success", text: r.message });
      setDone(true);
    } catch (err) {
      setState({ tone: "error", text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Choose a new password" footer={<Link className="font-semibold text-primary" href="/forgot-password">Request a new link</Link>}>
      {!token ? (
        <Notice tone="error">This reset link is incomplete. Request a new one.</Notice>
      ) : done ? (
        <div className="space-y-4">
          {state && <Notice tone={state.tone}>{state.text}</Notice>}
          <Button asChild className="w-full"><Link href="/login">Go to log in</Link></Button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {state && <Notice tone={state.tone}>{state.text}</Notice>}
          <Field id="password" label="New password" type="password" autoComplete="new-password" required minLength={6} />
          <Field id="confirm" label="Confirm new password" type="password" autoComplete="new-password" required minLength={6} />
          <Button type="submit" className="w-full" disabled={busy}>{busy ? "Saving…" : "Update password"}</Button>
        </form>
      )}
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return <Suspense><ResetForm /></Suspense>;
}
