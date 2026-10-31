"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Bell, Gift, LifeBuoy, ShieldCheck, Sparkles, Users, Wallet } from "lucide-react";
import { Badge, EmptyState, ErrorState, Notice, Skeleton } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/auth-shell";
import { FreeSpin } from "@/components/free-spin";
import { WalletBody } from "@/components/wallet-panel";
import { api, errorMessage } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { useAuth } from "@/lib/auth";
import { cn, formatDate } from "@/lib/utils";

const TABS = [
  ["overview", "Overview", Sparkles], ["wallet", "Wallet", Wallet], ["rewards", "Rewards", Gift],
  ["notifications", "Notifications", Bell], ["support", "Support", LifeBuoy], ["security", "Security", ShieldCheck],
] as const;

function Dashboard() {
  const router = useRouter();
  const params = useSearchParams();
  const { player, loading } = useAuth();
  const tab = params.get("tab") ?? "overview";

  useEffect(() => { if (!loading && !player) router.replace("/login"); }, [loading, player, router]);
  if (loading || !player) return <div className="container-x py-10"><Skeleton className="h-96" /></div>;

  return (
    <div className="container-x py-10">
      <div className="mb-8">
        <p className="text-sm font-semibold uppercase tracking-wider text-primary">Dashboard</p>
        <h1 className="text-3xl font-extrabold">Hi, {player.username}</h1>
      </div>
      <div className="grid gap-6 lg:grid-cols-[14rem_1fr]">
        <nav aria-label="Dashboard" className="flex gap-1 overflow-x-auto lg:flex-col">
          {TABS.map(([key, label, Icon]) => (
            <Link key={key} href={`/dashboard?tab=${key}`} scroll={false}
              className={cn("flex shrink-0 items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition",
                tab === key ? "bg-brand-gradient text-white shadow-lift" : "text-ink/80 hover:bg-white")}>
              <Icon className="h-4 w-4" />{label}
            </Link>
          ))}
        </nav>
        <section className="min-w-0">
          {tab === "overview" && <Overview />}
          {tab === "wallet" && <WalletTab />}
          {tab === "rewards" && <RewardsTab />}
          {tab === "notifications" && <NotificationsTab />}
          {tab === "support" && <SupportTab />}
          {tab === "security" && <SecurityTab />}
        </section>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return <Suspense><Dashboard /></Suspense>;
}

function Card({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="surface p-6">
      <div className="mb-4 flex items-center justify-between gap-3"><h2 className="font-bold">{title}</h2>{action}</div>
      {children}
    </div>
  );
}

function VerifyEmailBox() {
  const [msg, setMsg] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true); setMsg(null);
    try { const r = await api<{ message: string }>("/auth/verify-email/request", { method: "POST" }); setMsg({ tone: "success", text: r.message }); }
    catch (e) { setMsg({ tone: "error", text: errorMessage(e) }); } finally { setBusy(false); }
  };
  return (
    <div className="mt-4 space-y-2 rounded-xl border border-line p-3 text-sm">
      <p className="font-semibold">Verify your email to unlock bonuses</p>
      <ul className="list-disc space-y-0.5 pl-5 text-muted">
        <li><b className="text-ink">50% signup bonus</b> on the first cash you add to any one game</li>
        <li><b className="text-ink">10% bonus</b> on every cash add after that</li>
        <li>Bonus is added <b className="text-ink">directly into your game</b> and does not change your cashout range</li>
      </ul>
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <Button size="sm" onClick={send} disabled={busy}>{busy ? "Sending…" : "Send confirmation email"}</Button>
    </div>
  );
}

function Overview() {
  const { player, unread } = useAuth();
  const claims = useApi<{ items: { id: number; promotion: string; status: string; created_at: string }[] }>("/account/claims");
  const refs = useApi<{ code: string; counts: { pending: number; confirmed: number } }>("/referrals/me");
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <Card title="Account">
        <dl className="space-y-2 text-sm">
          <Row k="Username" v={player!.username} /><Row k="Email" v={player!.email} />
          <Row k="Email verified" v={player!.email_verified ? "Yes" : "Not verified"} />
        </dl>
        {!player!.email_verified ? <VerifyEmailBox /> : (
          <p className="mt-4 rounded-xl border border-line p-3 text-sm text-muted">Bonuses unlocked: <b className="text-ink">50% signup bonus</b> on your first cash added to any one game, then <b className="text-ink">10%</b> on every add, credited directly into the game.</p>
        )}
      </Card>
      <Card title="Referrals" action={<Link href="/refer" className="text-sm font-semibold text-primary">Open</Link>}>
        {refs.data ? (
          <p className="text-sm text-muted">Code <strong className="text-ink">{refs.data.code}</strong> · {refs.data.counts.confirmed} confirmed · {refs.data.counts.pending} pending</p>
        ) : <Skeleton className="h-10" />}
      </Card>
      <Card title="Promotion claims" action={<Link href="/bonus-zone" className="text-sm font-semibold text-primary">Browse</Link>}>
        {claims.loading ? <Skeleton className="h-16" /> : !claims.data?.items.length ? <p className="text-sm text-muted">You haven&apos;t claimed anything yet.</p> : (
          <ul className="divide-y divide-line text-sm">
            {claims.data.items.slice(0, 5).map((c) => (
              <li key={c.id} className="flex items-center justify-between py-2"><span>{c.promotion}<span className="ml-2 text-xs text-muted">{formatDate(c.created_at)}</span></span>
                <Badge tone={c.status === "fulfilled" ? "green" : c.status === "rejected" ? "red" : "amber"} className="capitalize">{c.status}</Badge></li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="Notifications" action={<Link href="/dashboard?tab=notifications" className="text-sm font-semibold text-primary">View</Link>}>
        <p className="text-sm text-muted">{unread > 0 ? `${unread} unread` : "You're all caught up."}</p>
      </Card>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return <div className="flex justify-between gap-4"><dt className="text-muted">{k}</dt><dd className="break-all font-medium">{v}</dd></div>;
}

function WalletTab() {
  return (
    <div className="space-y-5">
      <div className="rounded-3xl bg-[#111A32] p-6 text-white shadow-card"><WalletBody /></div>
      <CashRequests />
    </div>
  );
}

function CashRequests() {
  const { data, loading } = useApi<{ items: { id: number; game: string; amount: string; status: string; sandbox: boolean; note: string | null; created_at: string }[] }>("/account/cash-requests");
  if (loading || !data || data.items.length === 0) return null;
  const tone = (s: string) => (s === "completed" ? "green" : s === "failed" || s === "rejected" ? "red" : "amber");
  const label = (s: string) => ({ awaiting_staff: "Awaiting confirmation", processing: "Processing", needs_review: "Being checked", completed: "Completed", failed: "Failed", rejected: "Rejected" } as Record<string, string>)[s] ?? s;
  return (
    <Card title="Game cash requests">
      <ul className="divide-y divide-line text-sm">
        {data.items.map((r) => (
          <li key={r.id} className="flex items-center justify-between gap-3 py-2.5">
            <span>${r.amount} · {r.game}{r.sandbox && <span className="ml-2 text-xs text-muted">(sandbox)</span>}<span className="ml-2 text-xs text-muted">{formatDate(r.created_at)}</span></span>
            <Badge tone={tone(r.status)}>{label(r.status)}</Badge>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function RewardsTab() {
  const { refresh } = useAuth();
  return <FreeSpin onChanged={refresh} />;
}

function NotificationsTab() {
  const { refresh } = useAuth();
  const { data, loading, error, reload } = useApi<{ items: { id: number; title: string; body: string | null; read: boolean; created_at: string }[] }>("/notifications");
  const markRead = async () => { await api("/notifications/read", { method: "POST" }); await refresh(); reload(); };
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data) return <Skeleton className="h-48" />;
  return (
    <Card title="Notifications" action={data.items.some((n) => !n.read) && <Button size="sm" variant="secondary" onClick={markRead}>Mark all read</Button>}>
      {data.items.length === 0 ? <p className="text-sm text-muted">Nothing here yet.</p> : (
        <ul className="divide-y divide-line">
          {data.items.map((n) => (
            <li key={n.id} className="flex gap-3 py-3">
              <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", n.read ? "bg-line" : "bg-success")} />
              <div><p className="text-sm font-semibold">{n.title}</p>{n.body && <p className="text-sm text-muted">{n.body}</p>}<p className="mt-0.5 text-xs text-muted">{formatDate(n.created_at)}</p></div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function SupportTab() {
  const { data, loading, error, reload } = useApi<{ items: { id: number; subject: string; status: string; updated_at: string }[] }>("/support/tickets");
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data) return <Skeleton className="h-48" />;
  return (
    <Card title="Support tickets" action={<Button asChild size="sm"><Link href="/support">New ticket</Link></Button>}>
      {data.items.length === 0 ? <p className="text-sm text-muted">No tickets yet.</p> : (
        <ul className="divide-y divide-line">
          {data.items.map((t) => (
            <li key={t.id}><Link href={`/support?ticket=${t.id}`} className="flex items-center justify-between py-3 hover:text-primary">
              <span className="text-sm font-semibold">{t.subject}<span className="ml-2 text-xs font-normal text-muted">{formatDate(t.updated_at)}</span></span>
              <Badge tone={t.status === "answered" ? "green" : t.status === "closed" ? "gray" : "amber"} className="capitalize">{t.status}</Badge>
            </Link></li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function SecurityTab() {
  const { player, refresh } = useAuth();
  const [pw, setPw] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [em, setEm] = useState<{ tone: "error" | "success"; text: string } | null>(null);

  const changePassword = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      const r = await api<{ message: string }>("/account/password", { method: "POST", body: { current_password: f.get("current"), new_password: f.get("next") } });
      setPw({ tone: "success", text: r.message }); form.reset();
    } catch (err) { setPw({ tone: "error", text: errorMessage(err) }); }
  };
  const changeEmail = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await api("/account/profile", { method: "PATCH", body: { email: f.get("email"), current_password: f.get("current") } });
      setEm({ tone: "success", text: "Email updated." }); refresh();
    } catch (err) { setEm({ tone: "error", text: errorMessage(err) }); }
  };

  return (
    <div className="grid gap-5 md:grid-cols-2">
      <Card title="Change password">
        <form onSubmit={changePassword} className="space-y-4">
          {pw && <Notice tone={pw.tone}>{pw.text}</Notice>}
          <Field id="current" label="Current password" type="password" autoComplete="current-password" required />
          <Field id="next" label="New password" type="password" autoComplete="new-password" required minLength={6} />
          <Button type="submit">Update password</Button>
        </form>
      </Card>
      <Card title="Profile">
        <form onSubmit={changeEmail} className="space-y-4">
          {em && <Notice tone={em.tone}>{em.text}</Notice>}
          <Field id="email" label="Email" type="email" defaultValue={player!.email} required />
          <Field id="current" label="Current password" type="password" autoComplete="current-password" hint="Required to change your email." />
          <Button type="submit" variant="secondary">Save</Button>
        </form>
      </Card>
    </div>
  );
}
