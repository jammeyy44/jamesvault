"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  Activity, Banknote, BadgeCheck, Check, CreditCard, Disc3, Gamepad2, Gift, KeyRound, LayoutDashboard, LifeBuoy, Link2, LogOut, Pencil,
  Percent, Plus, ScrollText, Server, ShieldCheck, Sparkles, Ticket, Trash2, UserPlus, Users, Wallet, X,
} from "lucide-react";
import { Badge, EmptyState, ErrorState, Notice, Skeleton } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/logo";
import { api, ApiError, errorMessage, upload, type Role } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn, formatDate } from "@/lib/utils";


// ---------------------------------------------------------------- field config for content resources
type FieldDef = { name: string; label: string; type?: "text" | "textarea" | "number" | "bool" | "datetime" | "select" | "provider"; options?: string[]; required?: boolean };

const RESOURCES: Record<string, { label: string; title: string; fields: FieldDef[]; columns: string[] }> = {
  games: {
    label: "Game catalog", title: "name", columns: ["name", "category", "status", "is_featured", "launch_supported"],
    fields: [
      { name: "name", label: "Name", required: true }, { name: "slug", label: "Slug: short id used in links, lowercase with hyphens (e.g. game-vault)", required: true },
      { name: "provider_id", label: "Provider (game panel)", type: "provider" }, { name: "category", label: "Category label shown under the name (e.g. Slots, Table Games)" },
      { name: "image_url", label: "Artwork URL (or upload a thumbnail below)" }, { name: "download_url", label: "Download link for the game app (optional, shows the download button)" }, { name: "description", label: "Description", type: "textarea" },
      { name: "status", label: "Status", type: "select", options: ["active", "maintenance", "hidden"] },
      { name: "is_featured", label: "Featured", type: "bool" }, { name: "is_new", label: "New", type: "bool" },
      { name: "launch_supported", label: "Launch supported (needs a provider adapter)", type: "bool" },
      { name: "sort_order", label: "Sort order", type: "number" },
      { name: "cashout_min", label: "Cashout minimum ($, shown to players)", type: "number" }, { name: "cashout_max", label: "Cashout maximum ($, shown to players)", type: "number" },
    ],
  },
  promotions: {
    label: "Promotions", title: "title", columns: ["title", "promo_type", "state", "claim_rule"],
    fields: [
      { name: "title", label: "Title", required: true }, { name: "slug", label: "Slug: short id used in links, lowercase with hyphens (e.g. game-vault)", required: true },
      { name: "promo_type", label: "Type", type: "select", options: ["welcome", "first_deposit", "deposit_match", "free_play", "free_spins", "daily", "referral", "seasonal", "coupon"] },
      { name: "description", label: "Description", type: "textarea" }, { name: "eligibility", label: "Eligibility", type: "textarea" },
      { name: "reward_details", label: "Reward details", type: "textarea" }, { name: "terms", label: "Terms & conditions", type: "textarea" },
      { name: "image_url", label: "Artwork URL" },
      { name: "claim_rule", label: "Claim rule", type: "select", options: ["open", "new_player", "coupon", "deposit"] },
      { name: "new_player_days", label: "New-player window (days)", type: "number" }, { name: "coupon_code", label: "Coupon code" },
      { name: "repeat", label: "Repeat", type: "select", options: ["once", "daily"] },
      { name: "starts_at", label: "Starts", type: "datetime" }, { name: "ends_at", label: "Ends", type: "datetime" },
      { name: "is_active", label: "Enabled", type: "bool" },
    ],
  },
  "wheel-prizes": {
    label: "Free-spin prizes", title: "label", columns: ["label", "kind", "value", "weight", "boost_hours", "is_active"],
    fields: [
      { name: "kind", label: "Prize type", type: "select", options: ["diamonds", "freeplay", "boost_percent"], required: true },
      { name: "value", label: "Value (diamonds = count, freeplay = CENTS e.g. 200 = $2, boost = percent)", type: "number", required: true },
      { name: "weight", label: "Odds weight (chance = weight / total of active prizes)", type: "number", required: true },
      { name: "boost_hours", label: "Boost lasts (hours, boosts only)", type: "number" },
      { name: "label", label: "Label (optional, auto-filled)" },
      { name: "is_active", label: "Active", type: "bool" },
    ],
  },
};

const QUEUES: Record<string, { label: string; path: string; columns: string[]; actions?: { label: string; status: string; tone?: string }[]; patch: string; field?: string }> = {
  claims: { label: "Promotion claims", path: "/admin/claims?status=pending", columns: ["promotion", "player", "status", "created_at"], patch: "claims", actions: [{ label: "Fulfil", status: "fulfilled" }, { label: "Reject", status: "rejected", tone: "danger" }] },
  spins: { label: "Wheel rewards", path: "/admin/spins", columns: ["player", "prize", "status", "created_at"], patch: "spins", actions: [{ label: "Mark fulfilled", status: "fulfilled" }] },
  referrals: { label: "Referrals", path: "/admin/referrals", columns: ["referrer", "referred", "status", "created_at"], patch: "referrals", actions: [{ label: "Confirm", status: "confirmed" }, { label: "Reject", status: "rejected", tone: "danger" }] },
  players: { label: "Players", path: "/admin/players", columns: ["username", "email", "role", "status", "created_at"], patch: "players" },
  "cash-requests": { label: "Cash requests", path: "/admin/cash-requests?status=awaiting_staff,needs_review", columns: ["player", "game", "game_login", "amount", "status", "note", "created_at"], patch: "cash-requests", field: "action" },
  withdrawals: { label: "Cashouts", path: "/admin/withdrawals?status=pending_review,sending,needs_review,failed_at_provider,submitted", columns: ["player", "method", "amount", "destination", "status", "reference", "note", "created_at"], patch: "withdrawals", field: "action" },
  payments: { label: "Deposits", path: "/admin/payments", columns: ["player", "method", "amount", "status", "reference", "note", "created_at"], patch: "" },
  "provider-logs": { label: "Provider call log", path: "/admin/provider-logs", columns: ["created_at", "provider", "action", "success", "duration_ms", "detail"], patch: "" },
  audit: { label: "Audit log", path: "/admin/audit", columns: ["created_at", "actor", "action", "target", "ip"], patch: "" },
};

const ROLE_TABS: Record<Exclude<Role, "player">, string[]> = {
  superadmin: ["overview", "providers", "games", "promotions", "coupons", "wheel-prizes", "claims", "spins", "referrals", "cash-requests", "withdrawals", "payments", "unmatched", "payment-methods", "players", "tickets", "tokens", "provider-logs", "audit"],
  content: ["overview", "games", "promotions", "wheel-prizes", "claims", "spins"],
  support: ["overview", "claims", "spins", "referrals", "players", "tickets"],
};

const labelFor = (k: string) => RESOURCES[k]?.label ?? QUEUES[k]?.label ?? ({ tickets: "Support tickets", coupons: "Coupons", tokens: "API tokens", providers: "Providers", overview: "Overview", unmatched: "Unmatched payments", "payment-methods": "Payment methods" } as Record<string, string>)[k] ?? k;

const NAV_GROUPS: [string, string[]][] = [
  ["Dashboard", ["overview"]],
  ["Catalog & content", ["providers", "games", "promotions", "coupons", "wheel-prizes"]],
  ["Queues", ["claims", "spins", "referrals"]],
  ["Money", ["cash-requests", "withdrawals", "payments", "unmatched", "payment-methods"]],
  ["People", ["players", "tickets"]],
  ["System", ["tokens", "provider-logs", "audit"]],
];
const NAV_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  overview: LayoutDashboard, providers: Server, games: Gamepad2, promotions: Sparkles, coupons: Ticket, "wheel-prizes": Disc3,
  claims: BadgeCheck, spins: Gift, referrals: UserPlus, "cash-requests": Wallet, withdrawals: Banknote, payments: CreditCard,
  unmatched: Link2, "payment-methods": Percent, players: Users, tickets: LifeBuoy, tokens: KeyRound, "provider-logs": Activity, audit: ScrollText,
};

// ---------------------------------------------------------------- page
// One site, one login: staff sign in at /login like everyone else and see this panel because their account has a role.
export default function AdminPage() {
  const router = useRouter();
  const { player, loading, logout } = useAuth();
  const [tab, setTab] = useState("overview");

  useEffect(() => { if (!loading && !player) router.replace("/login"); }, [loading, player, router]);

  if (loading || !player) return <div className="container-x py-10"><Skeleton className="h-64" /></div>;
  if (!player.is_admin || player.role === "player") {
    return (
      <div className="container-x py-10">
        <EmptyState title="You don't have access to the admin panel">
          This area is for staff accounts. <Link href="/dashboard" className="font-semibold text-primary">Back to your dashboard</Link>
        </EmptyState>
      </div>
    );
  }
  const role = player.role as Exclude<Role, "player">;

  return (
    <div className="container-x py-8">
      <div className="relative mb-6 overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-r from-[#1b1740] via-[#121a36] to-[#0e1a2e] p-5 sm:p-6 shadow-card">
        <div className="pointer-events-none absolute -right-10 -top-16 h-52 w-52 rounded-full bg-purple-500/20 blur-3xl" />
        <div className="relative flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-[#8B5CF6] to-[#4F46E5] shadow-lift"><ShieldCheck className="h-6 w-6 text-white" /></span>
            <div>
              <h1 className="text-2xl font-black tracking-tight">Admin panel</h1>
              <p className="text-sm text-slate-400">Signed in as <b className="text-slate-200">{player.username}</b> <span className="ml-1 rounded-full border border-purple-400/30 bg-purple-400/10 px-2.5 py-0.5 text-xs font-bold capitalize text-purple-300">{role}</span></p>
            </div>
          </div>
          <Button variant="secondary" size="sm" onClick={async () => { await logout(); router.push("/"); }}><LogOut className="h-4 w-4" />Sign out</Button>
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-[15rem_1fr]">
        <nav className="lg:sticky lg:top-24 lg:self-start" aria-label="Admin sections">
          <div className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:gap-4 lg:overflow-visible lg:rounded-3xl lg:border lg:border-white/10 lg:bg-[#0F1424] lg:p-3 lg:shadow-card">
            {NAV_GROUPS.map(([group, keys]) => {
              const visible = keys.filter((k) => ROLE_TABS[role].includes(k));
              if (!visible.length) return null;
              return (
                <div key={group} className="flex gap-1.5 lg:flex-col lg:gap-1">
                  <p className="hidden px-3 pb-1 pt-1 text-[10px] font-extrabold uppercase tracking-[0.14em] text-slate-500 lg:block">{group}</p>
                  {visible.map((k) => {
                    const Icon = NAV_ICONS[k] ?? Activity;
                    const on = tab === k;
                    return (
                      <button key={k} onClick={() => setTab(k)} aria-current={on}
                        className={cn("group relative flex shrink-0 items-center gap-2.5 whitespace-nowrap rounded-xl px-3.5 py-2.5 text-left text-sm font-semibold transition",
                          on ? "bg-gradient-to-r from-[#7C3AED] to-[#4F46E5] text-white shadow-lift" : "text-slate-300 hover:bg-white/5 hover:text-white")}>
                        <Icon className={cn("h-4 w-4 shrink-0", on ? "text-white" : "text-slate-500 group-hover:text-sky-300")} />
                        {labelFor(k)}
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </nav>
        <section className="min-w-0">
          {tab === "overview" ? <Overview /> : tab === "providers" ? <Providers /> : tab === "unmatched" ? <Unmatched /> : tab === "payment-methods" ? <PaymentMethods /> : RESOURCES[tab] ? <ResourceManager key={tab} name={tab} /> : tab === "tickets" ? <Tickets /> : tab === "coupons" ? <Coupons /> : tab === "tokens" ? <Tokens /> : QUEUES[tab] ? <Queue key={tab} name={tab} role={role} /> : null}
        </section>
      </div>
    </div>
  );
}

const STAT_ICONS: [RegExp, React.ComponentType<{ className?: string }>, string][] = [
  [/player|user/, Users, "from-sky-500/25 to-sky-500/5 text-sky-300"],
  [/withdraw|cashout|payout/, Banknote, "from-amber-500/25 to-amber-500/5 text-amber-300"],
  [/deposit|payment|revenue/, CreditCard, "from-emerald-500/25 to-emerald-500/5 text-emerald-300"],
  [/ticket|support/, LifeBuoy, "from-rose-500/25 to-rose-500/5 text-rose-300"],
  [/claim|promotion/, BadgeCheck, "from-purple-500/25 to-purple-500/5 text-purple-300"],
  [/game|provider/, Gamepad2, "from-indigo-500/25 to-indigo-500/5 text-indigo-300"],
];

function Overview() {
  const [d, setD] = useState<Record<string, number> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api("/admin/overview").then(setD).catch((e) => setErr(errorMessage(e))); }, []);
  if (err) return <ErrorState message={err} />;
  if (!d) return <Skeleton className="h-40" />;
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
      {Object.entries(d).map(([k, v]) => {
        const [, Icon, tone] = STAT_ICONS.find(([re]) => re.test(k)) ?? [/./, Activity, "from-slate-500/25 to-slate-500/5 text-slate-300"];
        return (
          <div key={k} className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#0F1424] p-5 shadow-card transition hover:-translate-y-0.5 hover:border-white/20">
            <span className={cn("grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br", tone)}><Icon className="h-5 w-5" /></span>
            <p className="mt-4 text-3xl font-black tabular-nums tracking-tight">{v}</p>
            <p className="mt-0.5 text-xs font-semibold capitalize text-slate-400">{k.replace(/_/g, " ")}</p>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------- generic helpers
function useList(path: string) {
  const [items, setItems] = useState<any[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => { setError(null); api<{ items: any[] }>(path).then((r) => setItems(r.items)).catch((e) => setError(errorMessage(e))); }, [path]);
  useEffect(load, [load]);
  return { items, error, reload: load };
}

const STATUS_TONES: Record<string, string> = {
  active: "green", completed: "green", paid: "green", fulfilled: "green", confirmed: "green", approved: "green", open: "blue", answered: "blue",
  pending: "amber", pending_review: "amber", awaiting_staff: "amber", processing: "amber", sending: "amber", submitted: "blue", needs_review: "amber",
  failed: "red", rejected: "red", suspended: "red", cancelled: "gray", refunded: "gray", closed: "gray", hidden: "gray", reversed: "gray",
  superadmin: "violet", support: "blue", content: "blue", player: "gray",
};
const PILL: Record<string, string> = {
  green: "bg-emerald-400/10 text-emerald-300 border-emerald-400/25", amber: "bg-amber-400/10 text-amber-300 border-amber-400/25",
  red: "bg-rose-500/10 text-rose-300 border-rose-400/25", blue: "bg-sky-400/10 text-sky-300 border-sky-400/25",
  gray: "bg-white/5 text-slate-300 border-white/10", violet: "bg-purple-400/10 text-purple-300 border-purple-400/25",
};

function Cell({ v, col }: { v: any; col?: string }) {
  if (typeof v === "boolean") return v ? <Check className="h-4 w-4 text-emerald-400" /> : <X className="h-4 w-4 text-slate-500" />;
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}T/.test(v)) return <span className="whitespace-nowrap text-slate-300">{formatDate(v)}</span>;
  if (typeof v === "string" && (col === "status" || col === "role" || col === "bonus_kind")) {
    const tone = STATUS_TONES[v] ?? "gray";
    return <span className={cn("inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-bold capitalize", PILL[tone])}>{v.replace(/_/g, " ")}</span>;
  }
  return <>{v ?? <span className="text-slate-600">—</span>}</>;
}

function Table({ columns, rows, actions }: { columns: string[]; rows: any[]; actions?: (row: any) => React.ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10 bg-[#0F1424] shadow-card">
      <table className="w-full text-left text-sm">
        <thead><tr className="border-b border-white/10 bg-[#141B2E] text-[11px] uppercase tracking-wider text-slate-400">
          {columns.map((c) => <th key={c} className="whitespace-nowrap px-4 py-3 font-bold">{c.replace(/_/g, " ")}</th>)}{actions && <th />}
        </tr></thead>
        <tbody className="divide-y divide-white/5">
          {rows.map((r) => (
            <tr key={r.id} className="transition hover:bg-white/[0.03]">{columns.map((c) => <td key={c} className="px-4 py-3 text-slate-200"><Cell v={r[c]} col={c} /></td>)}{actions && <td className="px-4 py-3 text-right">{actions(r)}</td>}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------- CRUD
const toLocalInput = (iso?: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

function ResourceManager({ name }: { name: string }) {
  const cfg = RESOURCES[name];
  const { items, error, reload } = useList(`/admin/${name}`);
  const [editing, setEditing] = useState<any | "new" | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [providers, setProviders] = useState<{ id: number; name: string }[]>([]);
  useEffect(() => { if (cfg.fields.some((f) => f.type === "provider")) api<{ items: { id: number; name: string }[] }>("/admin/providers").then((r) => setProviders(r.items)).catch(() => {}); }, [cfg]);

  const remove = async (row: any) => {
    if (!confirm(`Delete "${row[cfg.title]}"? This cannot be undone.`)) return;
    try { await api(`/admin/${name}/${row.id}`, { method: "DELETE" }); reload(); setMsg(null); }
    catch (e) {
      if (e instanceof ApiError && e.code === "has_logins" && confirm(`${e.message}

Hide "${row[cfg.title]}" instead?`)) {
        try { await api(`/admin/${name}/${row.id}`, { method: "PATCH", body: { status: "hidden" } }); setMsg(null); reload(); } catch (err) { setMsg(errorMessage(err)); }
      } else setMsg(errorMessage(e));
    }
  };

  const save = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body: Record<string, unknown> = {};
    for (const fd of cfg.fields) {
      const raw = f.get(fd.name);
      if (fd.type === "bool") body[fd.name] = raw === "on";
      else if (fd.type === "number" || fd.type === "provider") body[fd.name] = raw === "" || raw === null ? null : Number(raw);
      else if (fd.type === "datetime") body[fd.name] = raw ? new Date(String(raw)).toISOString() : null;
      else body[fd.name] = raw === "" ? null : raw;
    }
    const thumb = name === "games" ? (f.get("thumbnail") as File | null) : null;
    try {
      const saved = editing === "new" ? await api(`/admin/${name}`, { method: "POST", body }) : await api(`/admin/${name}/${editing.id}`, { method: "PATCH", body });
      if (thumb && thumb.size > 0) {
        const form = new FormData(); form.append("file", thumb);
        try { await upload(`/admin/games/${saved.id ?? editing.id}/thumbnail`, form); }
        catch (err) { setMsg(`Saved, but the thumbnail was not uploaded: ${errorMessage(err)}`); reload(); return; }
      }
      setEditing(null); setMsg(null); reload();
    } catch (err) { setMsg(errorMessage(err)); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between"><h2 className="text-xl font-bold">{cfg.label}</h2>
        <Button size="sm" onClick={() => { setEditing("new"); setMsg(null); }}><Plus className="h-4 w-4" />New</Button></div>
      {msg && <Notice tone="error">{msg}</Notice>}
      {editing && (
        <form onSubmit={save} className="surface grid gap-4 p-5 md:grid-cols-2">
          {cfg.fields.map((fd) => {
            const val = editing === "new" ? undefined : editing[fd.name];
            if (fd.type === "bool") return <label key={fd.name} className="flex items-center gap-2 text-sm font-medium"><input type="checkbox" name={fd.name} defaultChecked={!!val} className="h-4 w-4 accent-primary" />{fd.label}</label>;
            return (
              <div key={fd.name} className={fd.type === "textarea" ? "md:col-span-2" : ""}>
                <label htmlFor={`f-${fd.name}`} className="label">{fd.label}</label>
                {fd.type === "textarea" ? <textarea id={`f-${fd.name}`} name={fd.name} defaultValue={val ?? ""} rows={3} className="field" />
                  : fd.type === "provider" ? <select id={`f-${fd.name}`} name={fd.name} defaultValue={val ?? ""} className="field"><option value="">No provider</option>{providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
                  : fd.type === "select" ? <select id={`f-${fd.name}`} name={fd.name} defaultValue={val ?? fd.options![0]} className="field">{fd.options!.map((o) => <option key={o}>{o}</option>)}</select>
                  : <input id={`f-${fd.name}`} name={fd.name} className="field" required={fd.required && editing === "new"}
                      type={fd.type === "number" ? "number" : fd.type === "datetime" ? "datetime-local" : "text"}
                      defaultValue={fd.type === "datetime" ? toLocalInput(val) : val ?? ""} />}
              </div>
            );
          })}
          {name === "games" && (
            <div className="md:col-span-2">
              <label htmlFor="f-thumbnail" className="label">Thumbnail (PNG, JPEG or WebP, up to 2 MB)</label>
              <div className="flex items-center gap-4">
                {editing !== "new" && editing.image_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={editing.image_url} alt="Current thumbnail" className="h-16 w-16 rounded-xl object-cover" />
                )}
                <input id="f-thumbnail" name="thumbnail" type="file" accept="image/png,image/jpeg,image/webp" className="field" />
              </div>
            </div>
          )}
          <div className="flex gap-2 md:col-span-2"><Button type="submit">Save</Button><Button type="button" variant="secondary" onClick={() => setEditing(null)}>Cancel</Button></div>
        </form>
      )}
      {error ? <ErrorState message={error} onRetry={reload} /> : !items ? <Skeleton className="h-40" /> : items.length === 0 ? <EmptyState title={`No ${cfg.label.toLowerCase()} yet`} /> : (
        <Table columns={cfg.columns} rows={items} actions={(r) => (
          <span className="inline-flex gap-1">
            <button aria-label="Edit" className="rounded-lg p-2 text-slate-300 transition hover:bg-white/10 hover:text-white" onClick={() => { setEditing(r); setMsg(null); }}><Pencil className="h-4 w-4" /></button>
            <button aria-label="Delete" className="rounded-lg p-2 text-rose-400 transition hover:bg-rose-500/10" onClick={() => remove(r)}><Trash2 className="h-4 w-4" /></button>
          </span>
        )} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------- one player, everything
function MiniTable({ title, cols, rows }: { title: string; cols: [string, string][]; rows: any[] }) {
  return (
    <section>
      <h4 className="mb-2 flex items-center gap-2 text-sm font-extrabold text-white"><span className="h-4 w-1 rounded-full bg-gradient-to-b from-[#8B5CF6] to-[#38BDF8]" />{title} <span className="rounded-full bg-white/10 px-2 py-0.5 text-[11px] font-bold text-slate-300">{rows.length}</span></h4>
      {rows.length === 0 ? <p className="rounded-xl border border-dashed border-white/10 px-4 py-3 text-sm text-slate-500">Nothing yet.</p> : (
        <div className="overflow-x-auto rounded-xl border border-white/10 bg-[#0C1120]"><table className="w-full text-left text-xs">
          <thead><tr className="border-b border-white/10 bg-[#141B2E] uppercase tracking-wider text-slate-400">{cols.map(([, h]) => <th key={h} className="px-3 py-2 font-semibold">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-white/5">{rows.map((r, i) => <tr key={i} className="hover:bg-white/[0.03]">{cols.map(([k]) => <td key={k} className="px-3 py-2 text-slate-200"><Cell v={r[k]} col={k} /></td>)}</tr>)}</tbody>
        </table></div>
      )}
    </section>
  );
}

function Stat({ k, v }: { k: string; v: any }) {
  return <div className="rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.06] to-white/[0.02] p-3.5"><p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{k}</p><p className="mt-1 break-all text-base font-extrabold text-white">{v ?? "—"}</p></div>;
}

function PlayerDetails({ id, onClose }: { id: number; onClose: () => void }) {
  const [d, setD] = useState<any | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api<any>(`/admin/players/${id}/profile`).then(setD).catch((e) => setErr(errorMessage(e))); }, [id]);
  return (
    <div className="fixed inset-0 z-[70] overflow-y-auto bg-black/75 p-3 backdrop-blur-sm sm:p-6" role="dialog" aria-modal="true" aria-label="Player details" onClick={onClose}>
      <div className="mx-auto my-4 max-w-5xl space-y-5 rounded-3xl border border-white/10 bg-[#0B0F1C] p-5 shadow-[0_30px_80px_rgba(0,0,0,0.7)] sm:p-7" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <h3 className="text-xl font-black tracking-tight">Player details{d ? <span className="text-sky-300"> · {d.player.username}</span> : ""}</h3>
          <Button size="sm" variant="secondary" onClick={onClose}>Close</Button>
        </div>
        {err ? <ErrorState message={err} onRetry={onClose} /> : !d ? <Skeleton className="h-60" /> : (<>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat k="Email" v={d.player.email} /><Stat k="Email verified" v={d.player.email_verified ? "Yes" : "No"} />
            <Stat k="Status / role" v={`${d.player.status} / ${d.player.role}`} /><Stat k="Joined" v={formatDate(d.player.created_at)} />
            <Stat k="Last login" v={d.player.last_login_at ? formatDate(d.player.last_login_at) : null} /><Stat k="Referred by" v={d.player.referred_by} />
            <Stat k="Wallet" v={`$${d.player.wallet}`} /><Stat k="Bonus balance" v={`$${d.player.bonus_balance}`} />
          </div>
          <div className="rounded-2xl border border-amber-300/25 bg-gradient-to-r from-amber-300/10 to-transparent p-4 text-sm">
            <p className="font-extrabold text-amber-200">Signup bonus (50%)</p>
            {d.signup_bonus.claimed
              ? <p>Claimed {d.signup_bonus.claimed_at ? formatDate(d.signup_bonus.claimed_at) : ""}{d.signup_bonus.game ? <> on <b>{d.signup_bonus.game}</b>: cash added ${d.signup_bonus.cash_added}, bonus ${d.signup_bonus.bonus_amount} added straight to the game.</> : "."}</p>
              : <p className="text-slate-400">{d.signup_bonus.email_verified ? "Not claimed yet (email verified)." : "Not available: email not verified."}</p>}
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat k="Deposited" v={`$${d.totals.deposited}`} /><Stat k="Cash added to games" v={`$${d.totals.cash_added_to_games}`} />
            <Stat k="Game bonus received" v={`$${d.totals.game_bonus_received}`} /><Stat k="Cashed out of games (to wallet)" v={`$${d.totals.redeemed_to_wallet}`} />
            <Stat k="Withdrawals requested" v={`$${d.totals.withdrawals_requested}`} /><Stat k="Coupons used" v={`$${d.totals.coupon_total}`} />
            <Stat k="Referral earnings" v={`$${d.totals.referral_earned}`} /><Stat k="Diamonds" v={d.player.diamonds} />
          </div>
          <MiniTable title="Games & logins created" cols={[["game", "Game"], ["login_username", "Login"], ["status", "Status"], ["login_created_at", "Created"], ["cash_added", "Cash added"], ["bonus_added", "Bonus"], ["adds", "Adds"], ["cashed_out", "Cashed out"], ["cashouts", "Cashouts"]]} rows={d.games} />
          <MiniTable title="Cash added to games" cols={[["at", "When"], ["game", "Game"], ["amount", "Cash"], ["bonus", "Bonus"], ["bonus_kind", "Bonus type"], ["source", "From"], ["status", "Status"]]} rows={d.cash_adds} />
          <MiniTable title="Deposits" cols={[["at", "When"], ["amount", "Amount"], ["method", "Method"], ["bonus", "Bonus"], ["status", "Status"]]} rows={d.deposits} />
          <MiniTable title="Game cashouts (game to wallet)" cols={[["at", "When"], ["game", "Game"], ["game_balance", "Game balance"], ["payout", "Paid to wallet"], ["voided", "Voided"], ["status", "Status"]]} rows={d.redeems} />
          <MiniTable title="Withdrawals" cols={[["at", "When"], ["amount", "Amount"], ["method", "Method"], ["status", "Status"]]} rows={d.withdrawals} />
          <MiniTable title="Coupons used" cols={[["at", "When"], ["code", "Code"], ["amount", "Amount"]]} rows={d.coupons} />
          <MiniTable title="People they referred" cols={[["at", "When"], ["username", "Player"], ["status", "Status"], ["reward", "Referral bonus"]]} rows={d.referrals} />
        </>)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- queues
function Queue({ name, role }: { name: string; role: Role }) {
  const q = QUEUES[name];
  const { items, error, reload } = useList(q.path);
  const [msg, setMsg] = useState<string | null>(null);
  const [detailId, setDetailId] = useState<number | null>(null);
  const act = async (id: number, status: string) => {
    try { await api(`/admin/${q.patch}/${id}`, { method: "PATCH", body: { [q.field ?? "status"]: status } }); reload(); } catch (e) { setMsg(errorMessage(e)); }
  };
  const setRole = async (id: number, next: string) => {
    if (!confirm(`Change this account's role to "${next}"?`)) { reload(); return; }
    try { await api(`/admin/players/${id}`, { method: "PATCH", body: { role: next } }); reload(); } catch (e) { setMsg(errorMessage(e)); reload(); }
  };
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">{q.label}</h2>
      {detailId !== null && <PlayerDetails id={detailId} onClose={() => setDetailId(null)} />}
      {msg && <Notice tone="error">{msg}</Notice>}
      {error ? <ErrorState message={error} onRetry={reload} /> : !items ? <Skeleton className="h-40" /> : items.length === 0 ? <EmptyState title="Nothing to show" /> : (
        <Table columns={q.columns} rows={items} actions={
          name === "players"
            ? (r) => (
              <span className="inline-flex items-center gap-2">
                <Button size="sm" variant="secondary" onClick={() => setDetailId(r.id)}>Details</Button>
                {role === "superadmin" && (
                  <select aria-label={`Role for ${r.username}`} className="field w-auto py-1.5" value={r.role} onChange={(e) => setRole(r.id, e.target.value)}>
                    {["player", "support", "content", "superadmin"].map((o) => <option key={o}>{o}</option>)}
                  </select>
                )}
                <Button size="sm" variant="secondary" onClick={() => act(r.id, r.status === "active" ? "suspended" : "active")}>{r.status === "active" ? "Suspend" : "Restore"}</Button>
              </span>
            )
            : name === "cash-requests"
              ? (r) => <CashActions row={r} onAct={act} />
            : name === "withdrawals"
              ? (r) => <WithdrawalActions row={r} onAct={act} />
            : q.actions && ((r) => r.status === "pending" ? <span className="inline-flex gap-2">{q.actions!.map((a) => <Button key={a.status} size="sm" variant={a.tone === "danger" ? "danger" : "secondary"} onClick={() => act(r.id, a.status)}>{a.label}</Button>)}</span> : null)
        } />
      )}
    </div>
  );
}

function Tickets() {
  const { items, error, reload } = useList("/admin/tickets");
  const [open, setOpen] = useState<any>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const view = async (id: number) => setOpen(await api(`/admin/tickets/${id}`));
  const reply = async (form: HTMLFormElement, close: boolean) => {
    try { await api(`/admin/tickets/${open.id}/reply`, { method: "POST", body: { message: new FormData(form).get("message"), close } }); form.reset(); reload(); view(open.id); }
    catch (err) { setMsg(errorMessage(err)); }
  };
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Support tickets</h2>
      {error ? <ErrorState message={error} onRetry={reload} /> : !items ? <Skeleton className="h-40" /> : items.length === 0 ? <EmptyState title="No tickets" /> :
        <Table columns={["id", "subject", "email", "status", "updated_at"]} rows={items} actions={(r) => <Button size="sm" variant="secondary" onClick={() => view(r.id)}>Open</Button>} />}
      {open && (
        <div className="surface space-y-3 p-5">
          <h3 className="font-bold">{open.subject} <Badge className="ml-2 capitalize">{open.status}</Badge></h3>
          <ul className="space-y-2">{open.messages.map((m: any, i: number) => <li key={i} className={cn("rounded-xl p-3 text-sm", m.author === "staff" ? "bg-soft" : "border border-line")}><strong className="capitalize">{m.author}</strong> · <span className="text-xs text-muted">{formatDate(m.created_at)}</span><p className="mt-1 whitespace-pre-line">{m.body}</p></li>)}</ul>
          {msg && <Notice tone="error">{msg}</Notice>}
          <form onSubmit={(e) => { e.preventDefault(); reply(e.currentTarget, false); }} className="space-y-2">
            <textarea name="message" rows={3} required className="field" aria-label="Reply" />
            <div className="flex gap-2"><Button type="submit">Send reply</Button>
              <Button type="button" variant="secondary" onClick={(e) => { const f = e.currentTarget.form!; if (f.reportValidity()) reply(f, true); }}>Reply &amp; close</Button></div>
          </form>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- coupons
function Coupons() {
  const { items, error, reload } = useList("/admin/coupons");
  const [scope, setScope] = useState<"many" | "single">("many");
  const [msg, setMsg] = useState<string | null>(null);
  const [made, setMade] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const val = (k: string) => String(f.get(k) ?? "").trim();
    const body: Record<string, unknown> = { amount: val("amount"), scope, code: val("code") || null, note: val("note") || null };
    if (scope === "single") body.player = val("player");
    else body.max_redemptions = val("max_redemptions") || null;
    if (val("expires_at")) body.expires_at = new Date(val("expires_at")).toISOString();
    setBusy(true); setMsg(null); setMade(null);
    try {
      const c = await api<{ code: string }>("/admin/coupons", { method: "POST", body });
      setMade(c.code); form.reset(); reload();
    } catch (err) { setMsg(errorMessage(err)); } finally { setBusy(false); }
  };
  const toggle = async (c: any) => {
    try { await api(`/admin/coupons/${c.id}`, { method: "PATCH", body: { is_active: !c.is_active } }); reload(); } catch (err) { setMsg(errorMessage(err)); }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Coupons</h2>
      <p className="text-sm text-muted">A coupon adds bonus cash to a player&apos;s bonus balance the moment they enter it. Every account can use a code only once.</p>
      {msg && <Notice tone="error">{msg}</Notice>}
      {made && <Notice tone="success">Coupon created. Share this code: <code className="select-all text-base font-extrabold" data-testid="new-coupon">{made}</code></Notice>}
      <form onSubmit={create} className="surface grid gap-4 p-5 md:grid-cols-2">
        <div>
          <label htmlFor="c-amount" className="label">Bonus amount ($)</label>
          <input id="c-amount" name="amount" required inputMode="decimal" placeholder="5" className="field" />
        </div>
        <fieldset>
          <legend className="label">Who can use it</legend>
          <div className="flex gap-2">
            {([["many", "Many people (once each)"], ["single", "One person only"]] as const).map(([v, label]) => (
              <label key={v} className={cn("flex-1 cursor-pointer rounded-xl border px-3 py-2 text-sm font-semibold", scope === v ? "border-primary bg-primary/10" : "border-line")}>
                <input type="radio" name="scope" value={v} checked={scope === v} onChange={() => setScope(v)} className="mr-2 accent-primary" />{label}
              </label>
            ))}
          </div>
        </fieldset>
        {scope === "single" ? (
          <div>
            <label htmlFor="c-player" className="label">Player&apos;s username or email</label>
            <input id="c-player" name="player" required className="field" />
          </div>
        ) : (
          <div>
            <label htmlFor="c-max" className="label">Maximum number of people (leave empty for no limit)</label>
            <input id="c-max" name="max_redemptions" type="number" min={1} className="field" />
          </div>
        )}
        <div>
          <label htmlFor="c-code" className="label">Code (leave empty to generate one)</label>
          <input id="c-code" name="code" maxLength={30} placeholder="e.g. SPRING5" className="field uppercase" />
        </div>
        <div>
          <label htmlFor="c-exp" className="label">Expires (optional)</label>
          <input id="c-exp" name="expires_at" type="datetime-local" className="field" />
        </div>
        <div>
          <label htmlFor="c-note" className="label">Note for staff (optional)</label>
          <input id="c-note" name="note" maxLength={120} className="field" />
        </div>
        <div className="md:col-span-2"><Button type="submit" disabled={busy}>Create coupon</Button></div>
      </form>
      {error ? <ErrorState message={error} onRetry={reload} /> : !items ? <Skeleton className="h-32" /> : items.length === 0 ? <EmptyState title="No coupons yet" /> : (
        <Table columns={["code", "amount", "who", "used", "expires_at", "is_active", "note"]}
          rows={items.map((c: any) => ({ ...c, who: c.scope === "single" ? `Only ${c.assigned_to}` : "Many people", used: c.max_redemptions ? `${c.redeemed_count} / ${c.max_redemptions}` : `${c.redeemed_count}` }))}
          actions={(r) => <Button size="sm" variant={r.is_active ? "danger" : "secondary"} onClick={() => toggle(r)}>{r.is_active ? "Turn off" : "Turn on"}</Button>} />
      )}
    </div>
  );
}

function Tokens() {
  const { items, error, reload } = useList("/admin/tokens");
  const [fresh, setFresh] = useState<string | null>(null);
  const create = async () => { const r = await api<{ token: string }>("/admin/tokens", { method: "POST", body: { days: 30 } }); setFresh(r.token); reload(); };
  const revoke = async (id: number) => { if (confirm("Revoke this token?")) { await api(`/admin/tokens/${id}`, { method: "DELETE" }); reload(); } };
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between"><h2 className="text-xl font-bold">API tokens</h2><Button size="sm" onClick={create}><Plus className="h-4 w-4" />New token (30 days)</Button></div>
      <p className="text-sm text-muted">Tokens authorize calls to the legacy provider endpoints (<code>Authorization: Bearer …</code>).</p>
      {fresh && <Notice tone="success">Copy this token now, it won&apos;t be shown again: <code className="break-all font-semibold">{fresh}</code></Notice>}
      {error ? <ErrorState message={error} onRetry={reload} /> : !items ? <Skeleton className="h-32" /> : items.length === 0 ? <EmptyState title="No active tokens" /> :
        <Table columns={["id", "hint", "valid_until", "usage_count"]} rows={items} actions={(r) => <Button size="sm" variant="danger" onClick={() => revoke(r.id)}>Revoke</Button>} />}
    </div>
  );
}

function CashActions({ row, onAct }: { row: any; onAct: (id: number, action: string) => void }) {
  const confirmThen = (msg: string, action: string) => { if (confirm(msg)) onAct(row.id, action); };
  if (row.status === "awaiting_staff") {
    return (
      <span className="inline-flex gap-2">
        <Button size="sm" onClick={() => confirmThen(`Only confirm after you have verified the payment.\n\nCredit $${row.amount} to ${row.game_login} (${row.game})? This runs once and cannot be undone.`, "confirm")}>Confirm payment &amp; credit</Button>
        <Button size="sm" variant="danger" onClick={() => confirmThen("Reject this request?", "reject")}>Reject</Button>
      </span>
    );
  }
  if (row.status === "needs_review") {
    return (
      <span className="inline-flex gap-2">
        <Button size="sm" variant="secondary" onClick={() => confirmThen("Check the provider panel first. Mark as credited?", "resolve_completed")}>Was credited</Button>
        <Button size="sm" variant="secondary" onClick={() => confirmThen("Check the provider panel first. Mark as NOT credited?", "resolve_failed")}>Was not credited</Button>
      </span>
    );
  }
  return null;
}

type Family = { value: string; label: string; games: string[] };

function Providers() {
  const { items, error, reload } = useList("/admin/providers");
  const [families, setFamilies] = useState<Family[]>([]);
  useEffect(() => { api<{ families: Family[] }>("/admin/providers").then((r) => setFamilies(r.families)).catch(() => {}); }, [items]);
  const famText = (f: Family) => `${f.games.join(", ")} (${f.label})`;
  const famByValue = (v: string) => families.find((f) => f.value === v);
  const [editing, setEditing] = useState<any | "new" | null>(null);
  const [msg, setMsg] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [testing, setTesting] = useState<number | null>(null);

  const save = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body: Record<string, unknown> = {
      name: f.get("name"), category: f.get("category"), base_url: f.get("base_url"), username: f.get("username"),
      is_active: f.get("is_active") === "on",
    };
    if (f.get("password")) body.password = f.get("password");
    try {
      if (editing === "new") await api("/admin/providers", { method: "POST", body });
      else await api(`/admin/providers/${editing.id}`, { method: "PATCH", body });
      setEditing(null); setMsg(null); reload();
    } catch (err) { setMsg({ tone: "error", text: errorMessage(err) }); }
  };
  const toggle = async (p: any) => { try { await api(`/admin/providers/${p.id}`, { method: "PATCH", body: { is_active: !p.is_active } }); reload(); } catch (e) { setMsg({ tone: "error", text: errorMessage(e) }); } };
  const remove = async (p: any) => {
    if (!confirm(`Delete provider "${p.name}"?`)) return;
    try { await api(`/admin/providers/${p.id}`, { method: "DELETE" }); reload(); } catch (e) { setMsg({ tone: "error", text: errorMessage(e) }); }
  };
  const test = async (p: any) => {
    setTesting(p.id); setMsg(null);
    try {
      const r = await api<{ ok: boolean; agent_balance: string | null; message: string | null }>(`/admin/providers/${p.id}/test`, { method: "POST" });
      setMsg(r.ok ? { tone: "success", text: `${p.name}: connected${r.agent_balance ? `, agent balance ${r.agent_balance}` : ""}${r.message ? ` (${r.message})` : ""}` } : { tone: "error", text: `${p.name}: ${r.message ?? "connection failed"}` });
    } catch (e) { setMsg({ tone: "error", text: errorMessage(e) }); } finally { setTesting(null); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between"><h2 className="text-xl font-bold">Providers</h2>
        <Button size="sm" onClick={() => { setEditing("new"); setMsg(null); }}><Plus className="h-4 w-4" />Add provider</Button></div>
      <p className="text-sm text-muted">A provider is a game panel we connect to with an agent login. Passwords are encrypted and can never be viewed again, only replaced. A provider switched off receives no traffic and its games show as under maintenance.</p>
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      {editing && (
        <form onSubmit={save} className="surface grid gap-4 p-5 md:grid-cols-2">
          <div><label htmlFor="p-name" className="label">Name</label><input id="p-name" name="name" className="field" required defaultValue={editing === "new" ? "" : editing.name} /></div>
          <div className="md:col-span-2"><label htmlFor="p-cat" className="label">Game group (which games share this connection type)</label>
            <select id="p-cat" name="category" className="field" defaultValue={editing === "new" ? "CATEGORY1" : editing.category}>{families.map((f) => <option key={f.value} value={f.value}>{famText(f)}</option>)}</select>
            <p className="mt-1 text-xs text-muted">Pick the group your game belongs to. It decides how we connect to its agent panel.</p></div>
          <div className="md:col-span-2"><label htmlFor="p-url" className="label">Panel URL (public https address)</label><input id="p-url" name="base_url" className="field" required placeholder="https://agent.example.com" defaultValue={editing === "new" ? "" : editing.base_url} /></div>
          <div><label htmlFor="p-user" className="label">Agent username</label><input id="p-user" name="username" className="field" required autoComplete="off" defaultValue={editing === "new" ? "" : editing.username} /></div>
          <div><label htmlFor="p-pass" className="label">Agent password</label><input id="p-pass" name="password" type="password" className="field" autoComplete="new-password" required={editing === "new"} placeholder={editing === "new" ? "" : "Leave blank to keep the current password"} /></div>
          <label className="flex items-center gap-2 text-sm font-medium"><input type="checkbox" name="is_active" defaultChecked={editing === "new" ? true : editing.is_active} className="h-4 w-4 accent-primary" />Enabled</label>
          <div className="flex gap-2 md:col-span-2"><Button type="submit">Save</Button><Button type="button" variant="secondary" onClick={() => setEditing(null)}>Cancel</Button></div>
        </form>
      )}
      {error ? <ErrorState message={error} onRetry={reload} /> : !items ? <Skeleton className="h-40" /> : items.length === 0 ? <EmptyState title="No providers yet">Add the first provider, then assign games to it in the game catalog.</EmptyState> : (
        <Table columns={["name", "group", "base_url", "username", "games", "is_active"]} rows={items.map((p) => ({ ...p, group: famByValue(p.category) ? famByValue(p.category)!.label + ": " + famByValue(p.category)!.games.join(", ") : p.category }))} actions={(p) => (
          <span className="inline-flex items-center gap-1">
            <Button size="sm" variant="secondary" disabled={testing === p.id} onClick={() => test(p)}>{testing === p.id ? "Testing…" : "Test"}</Button>
            <Button size="sm" variant="secondary" onClick={() => toggle(p)}>{p.is_active ? "Switch off" : "Switch on"}</Button>
            <button aria-label="Edit" className="rounded-lg p-2 text-slate-300 transition hover:bg-white/10 hover:text-white" onClick={() => { setEditing(p); setMsg(null); }}><Pencil className="h-4 w-4" /></button>
            <button aria-label="Delete" className="rounded-lg p-2 text-rose-400 transition hover:bg-rose-500/10" onClick={() => remove(p)}><Trash2 className="h-4 w-4" /></button>
          </span>
        )} />
      )}
    </div>
  );
}

function WithdrawalActions({ row, onAct }: { row: any; onAct: (id: number, action: string) => void }) {
  const go = (msg: string, action: string) => { if (confirm(msg)) onAct(row.id, action); };
  if (row.status === "pending_review") {
    return (
      <span className="inline-flex gap-2">
        <Button size="sm" onClick={() => go(`Send $${row.amount} to ${row.destination} via ${row.method}?\n\nThis pays out real money, runs once and cannot be undone.`, "approve")}>Approve &amp; send</Button>
        <Button size="sm" variant="danger" onClick={() => go("Reject and return the funds to the player's wallet?", "reject")}>Reject</Button>
      </span>
    );
  }
  if (row.status === "sending") {
    return <Button size="sm" onClick={() => go(`This cashout was left half-finished. Retry sending $${row.amount} to ${row.destination}?\n\nPaydora recognises the same order and will not pay twice.`, "retry_send")}>Retry sending</Button>;
  }
  if (row.status === "needs_review") {
    return (
      <span className="inline-flex gap-2">
        <Button size="sm" onClick={() => go("Retry sending? Paydora recognises the same order and will not pay twice.", "retry_send")}>Retry sending</Button>
        <Button size="sm" variant="secondary" onClick={() => go("Check the payment provider first. Mark as SENT?", "resolve_completed")}>Was sent</Button>
        <Button size="sm" variant="secondary" onClick={() => go("Check the payment provider first. Mark as NOT sent and refund the wallet?", "resolve_failed")}>Not sent (refund)</Button>
      </span>
    );
  }
  if (row.status === "failed_at_provider") {
    return <Button size="sm" variant="secondary" onClick={() => go("The player never received this payout. Return the funds to their wallet?", "credit_back")}>Credit back</Button>;
  }
  return null;
}

function Unmatched() {
  const { items, error, reload } = useList("/admin/unmatched-payments");
  const [msg, setMsg] = useState<string | null>(null);
  const [names, setNames] = useState<Record<number, string>>({});
  const act = async (id: number, action: "credit" | "dismiss") => {
    setMsg(null);
    try { await api(`/admin/unmatched-payments/${id}`, { method: "PATCH", body: { action, username: names[id] } }); reload(); } catch (e) { setMsg(errorMessage(e)); }
  };
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Unmatched payments</h2>
      <p className="text-sm text-muted">Payments or events we could not tie to an order we created (for example direct Chime payments). Nothing is credited automatically: memo text comes from a stranger&apos;s banking app, so verify who paid, then credit that player once.</p>
      {msg && <Notice tone="error">{msg}</Notice>}
      {error ? <ErrorState message={error} onRetry={reload} /> : !items ? <Skeleton className="h-32" /> : items.length === 0 ? <EmptyState title="Nothing needs attention" /> : (
        <div className="space-y-3">
          {items.map((r) => (
            <div key={r.id} className="surface flex flex-wrap items-center justify-between gap-3 p-4 text-sm">
              <div className="min-w-0">
                <p className="font-semibold">{r.event} {r.amount && <span>· ${r.amount}</span>}</p>
                <p className="break-all text-muted">{r.summary}</p>
                {r.memo && <p className="text-muted">Memo (untrusted text): <span className="font-mono">{r.memo}</span></p>}
              </div>
              <div className="flex items-center gap-2">
                {r.event === "deposit.paid" && r.amount && (
                  <>
                    <input aria-label="Player username" className="field w-40 py-2" placeholder="Player username" value={names[r.id] ?? ""} onChange={(e) => setNames((n) => ({ ...n, [r.id]: e.target.value }))} />
                    <Button size="sm" onClick={() => { if (confirm(`Credit $${r.amount} to "${names[r.id]}"? Only do this after verifying who paid.`)) act(r.id, "credit"); }} disabled={!names[r.id]}>Credit</Button>
                  </>
                )}
                <Button size="sm" variant="secondary" onClick={() => act(r.id, "dismiss")}>Dismiss</Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PaymentMethods() {
  const { items, error, reload } = useList("/admin/payment-methods");
  const [msg, setMsg] = useState<string | null>(null);
  const save = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await api("/admin/payment-methods", { method: "POST", body: { value: f.get("value"), label: f.get("label"), badge: f.get("badge"), badge_tone: f.get("badge_tone"), sort_order: Number(f.get("sort_order") || 0), is_enabled: f.get("is_enabled") === "on" } });
      form.reset(); setMsg(null); reload();
    } catch (err) { setMsg(errorMessage(err)); }
  };
  const remove = async (id: number) => { if (confirm("Remove this setting? The method falls back to the provider defaults.")) { await api(`/admin/payment-methods/${id}`, { method: "DELETE" }); reload(); } };
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Payment methods</h2>
      <p className="text-sm text-muted">Which methods players see comes from the payment provider. Here you only control presentation: a custom label, a badge such as &quot;No fee&quot; (only enter claims that are true), ordering, and hiding a method. Saving an existing method value updates it.</p>
      {msg && <Notice tone="error">{msg}</Notice>}
      <form onSubmit={save} className="surface grid gap-4 p-5 md:grid-cols-3">
        <div><label htmlFor="pm-value" className="label">Method value</label><input id="pm-value" name="value" required className="field" placeholder="cashapp, chime, card…" /></div>
        <div><label htmlFor="pm-label" className="label">Label (optional)</label><input id="pm-label" name="label" className="field" /></div>
        <div><label htmlFor="pm-badge" className="label">Badge text (optional)</label><input id="pm-badge" name="badge" className="field" maxLength={30} /></div>
        <div><label htmlFor="pm-tone" className="label">Badge colour</label><select id="pm-tone" name="badge_tone" className="field">{["green", "amber", "red", "blue"].map((t) => <option key={t}>{t}</option>)}</select></div>
        <div><label htmlFor="pm-order" className="label">Sort order</label><input id="pm-order" name="sort_order" type="number" className="field" defaultValue={0} /></div>
        <label className="flex items-center gap-2 self-end pb-3 text-sm font-medium"><input type="checkbox" name="is_enabled" defaultChecked className="h-4 w-4 accent-primary" />Visible to players</label>
        <div className="md:col-span-3"><Button type="submit">Save method</Button></div>
      </form>
      {error ? <ErrorState message={error} onRetry={reload} /> : !items ? <Skeleton className="h-24" /> : items.length === 0 ? <EmptyState title="No custom settings" /> : (
        <Table columns={["value", "label", "badge", "badge_tone", "sort_order", "is_enabled"]} rows={items} actions={(r) => (
          <button aria-label="Delete" className="rounded-lg p-2 text-rose-400 transition hover:bg-rose-500/10" onClick={() => remove(r.id)}><Trash2 className="h-4 w-4" /></button>
        )} />
      )}
    </div>
  );
}
