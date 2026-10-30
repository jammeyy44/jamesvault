"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { MessageSquare } from "lucide-react";
import { Badge, ErrorState, Notice, PageHeader, Skeleton } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/auth-shell";
import { api, errorMessage } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { useAuth } from "@/lib/auth";
import { cn, formatDate } from "@/lib/utils";

type Thread = { id: number; subject: string; status: string; messages: { author: "player" | "staff"; body: string; created_at: string }[] };

function Conversation({ id }: { id: string }) {
  const { data, loading, error, reload } = useApi<Thread>(`/support/tickets/${id}`);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const reply = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true); setMsg(null);
    try {
      await api(`/support/tickets/${id}/messages`, { method: "POST", body: { message: new FormData(form).get("message") } });
      form.reset(); reload();
    } catch (err) { setMsg(errorMessage(err)); } finally { setBusy(false); }
  };

  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data) return <Skeleton className="h-64" />;
  return (
    <div className="surface p-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="font-bold">{data.subject}</h2>
        <Badge tone={data.status === "answered" ? "green" : data.status === "closed" ? "gray" : "amber"} className="capitalize">{data.status}</Badge>
      </div>
      <ul className="space-y-3">
        {data.messages.map((m, i) => (
          <li key={i} className={cn("max-w-[85%] rounded-2xl px-4 py-3 text-sm", m.author === "staff" ? "bg-soft" : "ml-auto bg-brand-gradient text-white")}>
            <p className="whitespace-pre-line">{m.body}</p>
            <p className={cn("mt-1 text-[0.7rem]", m.author === "staff" ? "text-muted" : "text-white/70")}>{m.author === "staff" ? "Support" : "You"} · {formatDate(m.created_at)}</p>
          </li>
        ))}
      </ul>
      <form onSubmit={reply} className="mt-5 space-y-3">
        {msg && <Notice tone="error">{msg}</Notice>}
        <label htmlFor="message" className="label">Reply</label>
        <textarea id="message" name="message" rows={3} required maxLength={5000} className="field" />
        <Button type="submit" disabled={busy}>Send reply</Button>
      </form>
    </div>
  );
}

function NewTicket() {
  const { player } = useAuth();
  const [state, setState] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    setBusy(true); setState(null);
    try {
      await api("/support/tickets", { method: "POST", body: { subject: f.get("subject"), message: f.get("message"), email: f.get("email") || undefined } });
      form.reset();
      setState({ tone: "success", text: player ? "Ticket created. Follow the conversation from your dashboard." : "Thanks, we've received your message and will reply by email." });
    } catch (err) { setState({ tone: "error", text: errorMessage(err) }); } finally { setBusy(false); }
  };

  return (
    <form onSubmit={submit} className="surface space-y-4 p-6">
      <h2 className="flex items-center gap-2 font-bold"><MessageSquare className="h-5 w-5 text-primary" />Contact support</h2>
      {state && <Notice tone={state.tone}>{state.text}</Notice>}
      {!player && <Field id="email" label="Your email" type="email" required hint="We'll reply here." />}
      <Field id="subject" label="Subject" required minLength={3} maxLength={160} />
      <div>
        <label htmlFor="message" className="label">How can we help?</label>
        <textarea id="message" name="message" rows={5} required minLength={5} maxLength={5000} className="field" />
      </div>
      <Button type="submit" disabled={busy}>{busy ? "Sending…" : "Send message"}</Button>
    </form>
  );
}

function SupportInner() {
  const ticket = useSearchParams().get("ticket");
  const { player } = useAuth();
  return (
    <div className="container-x py-10">
      <PageHeader eyebrow="Help & Support" title="We're here to help">Send us a message and track the answer from your dashboard.</PageHeader>
      <div className="max-w-2xl space-y-6">
        {ticket && player ? <Conversation id={ticket} /> : <NewTicket />}
        {player && <p className="text-sm text-muted">Your earlier tickets live in your <Link href="/dashboard?tab=support" className="font-semibold text-primary">dashboard</Link>.</p>}
      </div>
    </div>
  );
}

export default function SupportPage() {
  return <Suspense><SupportInner /></Suspense>;
}
