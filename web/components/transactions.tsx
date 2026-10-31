"use client";

import { useMemo, useState } from "react";
import { ArrowDownToLine, ArrowUpFromLine, FileText, Gamepad2, RefreshCw, Trophy } from "lucide-react";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

type Order = {
  id: number; type: "deposit" | "cashout" | "redeem"; method: string; amount: string; status: string; created_at: string;
  bonus?: string | null; voided?: string | null;
};
type Cash = { id: number; game: string; amount: string; bonus: string; bonus_kind: string | null; source: string; status: string; created_at: string };

type Row = {
  key: string; kind: "deposit" | "cashout" | "redeem" | "add"; title: string; sub: string; amount: string; sign: "+" | "-"; status: string; at: string;
};

const money = (v: string | number) => `$${Number(v).toFixed(2)}`;
const FILTERS = [["all", "All"], ["deposit", "Deposits"], ["add", "Added to game"], ["redeem", "Game cashouts"], ["cashout", "Withdrawals"]] as const;

const STATUS: Record<string, string> = {
  paid: "green", completed: "green", submitted: "blue", sending: "amber", pending: "amber", pending_review: "amber", processing: "amber",
  needs_review: "amber", awaiting_staff: "amber", failed: "red", rejected: "red", cancelled: "gray", refunded: "gray",
};
const PILL: Record<string, string> = {
  green: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300", amber: "border-amber-400/25 bg-amber-400/10 text-amber-300",
  red: "border-rose-400/25 bg-rose-500/10 text-rose-300", blue: "border-sky-400/25 bg-sky-400/10 text-sky-300", gray: "border-white/10 bg-white/5 text-slate-300",
};
const ICON = {
  deposit: [ArrowDownToLine, "from-emerald-400/25 to-emerald-400/5 text-emerald-300"],
  cashout: [ArrowUpFromLine, "from-amber-400/25 to-amber-400/5 text-amber-300"],
  redeem: [Trophy, "from-fuchsia-400/25 to-fuchsia-400/5 text-fuchsia-300"],
  add: [Gamepad2, "from-sky-400/25 to-sky-400/5 text-sky-300"],
} as const;

function when(iso: string) {
  const d = new Date(iso);
  return `${d.toLocaleDateString(undefined, { day: "numeric", month: "short" })} · ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
}

/** The player's real activity: deposits, cash added to games (with bonus), game cashouts and withdrawals. */
export function Transactions({ className }: { className?: string }) {
  const hist = useApi<{ orders: Order[] }>("/wallet/history");
  const cash = useApi<{ items: Cash[] }>("/account/cash-requests");
  const [filter, setFilter] = useState<(typeof FILTERS)[number][0]>("all");

  const rows = useMemo<Row[]>(() => {
    const out: Row[] = [];
    for (const o of hist.data?.orders ?? []) {
      if (o.type === "deposit") out.push({ key: `d${o.id}`, kind: "deposit", title: "Deposit", sub: `${o.method}${o.bonus ? ` · +${money(o.bonus)} bonus` : ""}`, amount: o.amount, sign: "+", status: o.status, at: o.created_at });
      else if (o.type === "cashout") out.push({ key: `w${o.id}`, kind: "cashout", title: "Withdrawal", sub: o.method, amount: o.amount, sign: "-", status: o.status, at: o.created_at });
      else out.push({ key: `r${o.id}`, kind: "redeem", title: `Cashed out of ${o.method}`, sub: `Added to your wallet${o.voided ? ` · ${money(o.voided)} voided` : ""}`, amount: o.amount, sign: "+", status: o.status, at: o.created_at });
    }
    for (const c of cash.data?.items ?? []) {
      const bonus = Number(c.bonus) > 0 ? ` · +${money(c.bonus)} ${c.bonus_kind === "signup" ? "signup " : ""}bonus` : "";
      out.push({ key: `c${c.id}`, kind: "add", title: `Added to ${c.game}`, sub: `From ${c.source === "bonus" ? "bonus balance" : "wallet"}${bonus}`, amount: c.amount, sign: "-", status: c.status, at: c.created_at });
    }
    return out.sort((a, b) => (a.at < b.at ? 1 : -1)).slice(0, 60);
  }, [hist.data, cash.data]);

  const shown = rows.filter((r) => filter === "all" || r.kind === filter);
  const loading = hist.loading || cash.loading;

  return (
    <div data-testid="transactions" className={cn("rounded-3xl border border-white/10 bg-[#121829] p-4 shadow-xl sm:p-6", className)}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-base font-extrabold text-white"><FileText className="h-5 w-5 text-slate-400" />Transactions</h3>
        <button onClick={() => { hist.reload(); cash.reload(); }} aria-label="Refresh transactions" className="grid h-8 w-8 place-items-center rounded-full border border-white/10 text-slate-400 transition hover:bg-white/10 hover:text-white">
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
        </button>
      </div>
      <div className="mt-3 flex gap-1.5 overflow-x-auto pb-1">
        {FILTERS.map(([k, label]) => (
          <button key={k} onClick={() => setFilter(k)} aria-pressed={filter === k}
            className={cn("shrink-0 rounded-full border px-3 py-1.5 text-xs font-bold transition", filter === k ? "border-sky-400/50 bg-sky-400/15 text-sky-200" : "border-white/10 text-slate-400 hover:text-white")}>{label}</button>
        ))}
      </div>

      {loading && rows.length === 0 ? (
        <div className="mt-4 space-y-2">{[0, 1, 2].map((i) => <div key={i} className="h-14 animate-pulse rounded-2xl bg-white/5" />)}</div>
      ) : shown.length === 0 ? (
        <div className="grid min-h-[180px] place-items-center text-center">
          <div>
            <div className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl border border-white/10 bg-white/5 text-slate-400"><FileText className="h-7 w-7 stroke-[1.5]" /></div>
            <p className="text-sm font-bold text-slate-300">No transactions yet</p>
            <p className="mt-1 text-xs text-slate-400">Deposits, cash added to games, cashouts and withdrawals appear here.</p>
          </div>
        </div>
      ) : (
        <ul className="mt-3 divide-y divide-white/5">
          {shown.map((r) => {
            const [Icon, tone] = ICON[r.kind];
            const pill = PILL[STATUS[r.status] ?? "gray"];
            return (
              <li key={r.key} className="flex items-center gap-3 py-3">
                <span className={cn("grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br", tone)}><Icon className="h-5 w-5" /></span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold text-white">{r.title}</p>
                  <p className="truncate text-[11px] text-slate-400">{r.sub} · {when(r.at)}</p>
                </div>
                <div className="shrink-0 text-right">
                  <p className={cn("text-sm font-black tabular-nums", r.sign === "+" ? "text-emerald-300" : "text-slate-100")}>{r.sign}{money(r.amount)}</p>
                  <span className={cn("mt-0.5 inline-block rounded-full border px-2 py-0.5 text-[10px] font-bold capitalize", pill)}>{r.status.replace(/_/g, " ")}</span>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
