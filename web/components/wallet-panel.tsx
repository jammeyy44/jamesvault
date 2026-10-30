"use client";

import { CashoutLimitsModal } from "./cashout-limits-modal";
import { PaymentIcon } from "./payment-icon";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ArrowDownToLine, ArrowUpFromLine, FlaskConical, Pencil, Trash2, Wallet as WalletIcon, X } from "lucide-react";
import { Spinner } from "./ui/bits";
import { DepositBoostBanner, type Boost } from "./deposit-boost";
import { api, errorMessage } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

type Method = { id: string; value: string; name: string; badge: string | null; badge_tone: string | null; amounts: number[] | null };
type WalletState = {
  enabled: boolean; mode: "sandbox" | "live" | "disabled"; balance: string | null; reason?: string; notice: string | null;
  sandbox_notice: string | null; bonus_balance?: string; boost?: Boost | null; deposit_methods: Method[]; withdrawal_methods: Method[];
  cashout: { min: string; max: string }; deposit: { min: string; max: string }; payout_fields: Record<string, string>;
  cashout_rule?: { table: { deposit: string; min: string; max: string }[]; note: string; latest_deposit: string | null; row: number | null; min: string | null; max: string | null };
};
type Order = { id: number; type: "deposit" | "cashout" | "redeem"; voided?: string | null; method: string; amount: string; status: string; sandbox: boolean; payment_url?: string | null; bonus?: string | null; bonus_percent?: number | null; created_at: string };
type History = { orders: Order[]; ledger: { id: number; kind: string; bucket?: string; amount: string; balance_after: string; created_at: string }[] };

export const WALLET_EVENT = "jv-wallet-changed";
export const OPEN_WALLET_EVENT = "jv-open-wallet";
export const notifyWalletChanged = () => window.dispatchEvent(new Event(WALLET_EVENT));

const money = (v: string | number) => `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function deviceId() {
  try {
    let id = localStorage.getItem("jv-device");
    if (!id) { id = crypto.randomUUID().replace(/-/g, ""); localStorage.setItem("jv-device", id); }
    return id;
  } catch { return crypto.randomUUID().replace(/-/g, ""); }
}

const TONES: Record<string, string> = {
  green: "bg-emerald-400/15 text-emerald-300", amber: "bg-amber-400/20 text-amber-300",
  red: "bg-red-400/15 text-red-300", blue: "bg-electric/20 text-electric",
};
const STATUS_LABEL: Record<string, string> = {
  pending: "Awaiting payment", paid: "Paid", failed: "Failed", refunded: "Refunded", pending_review: "In review",
  sending: "Sending", submitted: "Sent for payout", completed: "Completed", cancelled: "Cancelled", rejected: "Rejected",
  needs_review: "Being checked", failed_at_provider: "Payout problem", credited_back: "Returned to wallet",
};
const KIND_LABEL: Record<string, string> = {
  deposit: "Deposit", refund: "Deposit refunded", withdrawal: "Cashout", withdrawal_refund: "Cashout returned",
  cash_to_game: "Added to game", cash_refund: "Game cash returned", adjustment: "Adjustment",
  deposit_bonus: "Deposit Boost bonus", deposit_bonus_reversal: "Bonus reversed (refund)", box_reward: "Lucky Shop reward",
};

function Tile({ m, active, onClick }: { m: Method; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} aria-pressed={active} aria-label={m.name}
      className={cn("relative rounded-2xl border p-4 text-left transition hover:-translate-y-0.5 active:scale-[0.98]", active ? "border-electric bg-gradient-to-b from-white/[0.12] to-white/[0.06] shadow-[0_8px_24px_rgba(56,189,248,0.18)]" : "border-white/[0.06] bg-gradient-to-b from-white/[0.07] to-white/[0.03] hover:from-white/[0.1] hover:to-white/[0.05]")}>
      {m.badge && <span className={cn("absolute right-3 top-3 rounded-full px-2 py-0.5 text-[0.65rem] font-bold", TONES[m.badge_tone ?? "green"] ?? TONES.green)}>{m.badge}</span>}
      <PaymentIcon value={m.value} name={m.name} />
      <span className="mt-5 block text-sm font-bold">{m.name}</span>
    </button>
  );
}

export function WalletBody() {
  const [w, setW] = useState<WalletState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"deposit" | "cashout">("deposit");
  const load = useCallback(async () => {
    try { setW(await api<WalletState>("/wallet")); setError(null); } catch (e) { setError(errorMessage(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const changed = useCallback(() => { load(); notifyWalletChanged(); }, [load]);

  if (error) return <p role="alert" className="rounded-2xl bg-red-500/15 p-4 text-sm text-red-200">{error}</p>;
  if (!w) return <div className="grid h-40 place-items-center"><Spinner className="h-6 w-6" /></div>;
  if (!w.enabled) {
    return (
      <div className="rounded-2xl bg-white/5 p-6 text-center">
        <WalletIcon className="mx-auto h-10 w-10 text-electric" />
        <p className="mt-3 font-bold">Wallet isn&apos;t available yet</p>
        <p className="mt-1 text-sm text-white/60">{w.reason ?? "Deposits and withdrawals will appear here once payments are enabled."}</p>
      </div>
    );
  }
  return (
    <div>
      {w.boost && <DepositBoostBanner boost={w.boost} onExpire={load} className="mb-3" />}
      <div className="rounded-3xl border border-white/10 bg-white/5 px-6 py-6 text-center">
        <p className="text-white/55">Balance</p>
        <p className="mt-1 text-5xl font-extrabold" data-testid="wallet-balance"><span className="text-electric">$</span>{Number(w.balance ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
        <div className="mx-auto mt-4 inline-flex items-center gap-2 rounded-full bg-[#1d2a4d] px-4 py-1.5 text-sm" title="Bonus balance can be added to games with Add Cash. It cannot be withdrawn.">
          <span className="text-white/60">Bonus balance</span>
          <span className="font-extrabold text-[#ffd966]" data-testid="bonus-balance">${Number(w.bonus_balance ?? 0).toFixed(2)}</span>
        </div>
      </div>
      {w.notice && <p role="alert" className="mt-3 rounded-2xl bg-amber-300/10 p-3 text-sm text-amber-100">{w.notice}</p>}
      <div role="tablist" className="mt-6 flex gap-8 border-b border-white/10">
        <button
          role="tab"
          aria-selected={tab === "deposit"}
          onClick={() => setTab("deposit")}
          className={cn("-mb-px pb-3 text-lg font-bold transition", tab === "deposit" ? "border-b-2 border-violet text-white" : "text-white/45 hover:text-white/80")}
        >
          Deposit
        </button>
        <button
          role="tab"
          aria-selected={tab === "cashout"}
          onClick={() => setTab("cashout")}
          className={cn("-mb-px pb-3 text-lg font-bold transition", tab === "cashout" ? "border-b-2 border-violet text-white" : "text-white/45 hover:text-white/80")}
        >
          Withdrawal
        </button>
      </div>
      <div className="mt-5">
        {tab === "deposit" && <Deposit w={w} onDone={changed} />}
        {tab === "cashout" && <Cashout w={w} onDone={changed} />}
      </div>
    </div>
  );
}

const inputCls = "w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none placeholder:text-white/35 focus:border-electric";
const primaryBtn = "inline-flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-electric px-5 font-bold text-ink transition hover:brightness-110 disabled:opacity-50";

function Deposit({ w, onDone }: { w: WalletState; onDone: () => void }) {
  const [method, setMethod] = useState<Method | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  if (w.deposit_methods.length === 0) return <p className="rounded-2xl bg-white/5 p-5 text-sm text-white/60">No deposit methods are available right now.</p>;

  return (
    <div>
      <div className="grid grid-cols-2 gap-3">
        {w.deposit_methods.map((m) => <Tile key={m.id} m={m} active={false} onClick={() => { setMsg(null); setMethod(m); }} />)}
      </div>
      {msg && <p role="status" className="mt-3 rounded-2xl bg-emerald-400/15 p-3 text-sm text-emerald-100">{msg}</p>}
      {method && (
        <DepositPopup method={method} limits={w.deposit} boost={w.boost ?? null} onBack={() => setMethod(null)}
          onDone={(text) => { setMethod(null); setMsg(text); onDone(); }} />
      )}
    </div>
  );
}

const roundCents = (n: number) => Math.round(n * 100) / 100;
const fmtAmount = (n: number) => `$${Number.isInteger(n) ? n : n.toFixed(2)}`;

/** Ask how much to deposit, then continue to the provider's payment page. Methods with a fixed list of accepted
 * amounts (the provider rejects anything else) snap the quick buttons to the next accepted amount. */
function DepositPopup({ method, limits, boost, onBack, onDone }: { method: Method; limits: { min: string; max: string }; boost: Boost | null; onBack: () => void; onDone: (text: string) => void }) {
  const fixed = method.amounts ? [...method.amounts].sort((a, b) => a - b) : null;
  const min = Number(limits.min), max = Number(limits.max);
  const start = fixed ? fixed[0] : Math.min(max, Math.max(min, 20));
  const [amount, setAmount] = useState<number>(start);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const attempt = useRef<{ k: string; key: string } | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !busy) onBack(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onBack, busy]);

  const snapUp = (t: number) => fixed!.find((a) => a >= t) ?? fixed![fixed!.length - 1];
  const clamp = (n: number) => Math.min(max, Math.max(0, roundCents(n)));
  const add = (n: number) => setAmount((a) => (fixed ? snapUp(a + n) : clamp(a + n)));
  const double = () => setAmount((a) => (fixed ? snapUp(a * 2) : clamp(a * 2)));
  const reset = () => { setAmount(fixed ? fixed[0] : 0); setEditing(false); };
  const valid = fixed ? fixed.includes(amount) : amount >= min && amount <= max;

  const submit = async () => {
    setBusy(true); setError(null);
    const k = `${method.id}:${amount}`;
    if (!attempt.current || attempt.current.k !== k) attempt.current = { k, key: crypto.randomUUID() };  // same key on retry: never a duplicate order
    try {
      const o = await api<Order>("/wallet/deposits", { method: "POST", body: { method_id: method.id, amount: amount.toFixed(2), idempotency_key: attempt.current.key, device_fingerprint: deviceId() } });
      attempt.current = null;
      if (o.payment_url) { window.location.href = o.payment_url; return; }  // pay on the provider's page
      onDone(o.status === "paid" ? `${money(o.amount)} added${o.bonus ? ` + ${money(o.bonus)} bonus` : ""}${o.sandbox ? " (sandbox test funds)" : ""}.` : "Order created. Your balance updates when the payment is confirmed.");
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  };

  const quick = "rounded-xl bg-[#1d2a4d] py-3 text-sm font-bold text-electric transition hover:bg-[#25356040] hover:brightness-125";
  return createPortal(
    <div data-modal-nested className="fixed inset-0 z-[70] grid place-items-center overflow-y-auto bg-ink/75 p-4 backdrop-blur-sm"
      onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onBack(); }}>
      <div role="dialog" aria-modal="true" aria-label={`${method.name} deposit`} className="my-auto w-full max-w-md rounded-3xl border border-white/10 bg-[#111A32] p-6 text-white shadow-2xl">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-2xl font-extrabold">{method.name}</h3>
            <p className="mt-1 text-white/60">Enter the deposit amount and go to the payment page</p>
          </div>
          <button onClick={onBack} aria-label="Close" className="rounded-full p-1 text-white/60 hover:text-white"><X className="h-6 w-6" /></button>
        </div>

        <p className="mt-6 text-center text-sm text-white/55">Enter deposit amount</p>
        <div className="mt-2 flex items-center justify-between rounded-2xl bg-white/5 px-5 py-4">
          {fixed ? <span className="w-5" /> : (
            <button onClick={() => setEditing((v) => !v)} aria-label="Edit amount" className="text-electric"><Pencil className="h-5 w-5" /></button>
          )}
          {editing && !fixed ? (
            <input autoFocus inputMode="decimal" aria-label="Amount in dollars" value={amount || ""} placeholder="0"
              onChange={(e) => { const v = e.target.value.replace(/[^0-9.]/g, ""); setAmount(v === "" ? 0 : clamp(Number(v) || 0)); }}
              onBlur={() => setEditing(false)} className="w-36 bg-transparent text-center text-4xl font-extrabold outline-none" />
          ) : (
            <p className="text-4xl font-extrabold" data-testid="deposit-amount">{fmtAmount(amount)}</p>
          )}
          <button onClick={reset} aria-label="Clear amount" className="text-white/60 hover:text-white"><X className="h-6 w-6" /></button>
        </div>

        <div className="mt-3 grid grid-cols-5 gap-2">
          {[5, 10, 25].map((n) => <button key={n} onClick={() => add(n)} className={quick}>+{n}</button>)}
          <button onClick={double} className={quick}>X2</button>
          <button onClick={reset} aria-label="Reset amount" className="grid place-items-center rounded-xl bg-red-500/15 text-red-300 hover:bg-red-500/25"><Trash2 className="h-5 w-5" /></button>
        </div>

        {fixed ? (
          <div className="mt-5">
            <p className="mb-2 text-sm font-semibold text-white/70">{method.name} accepts these amounts</p>
            <div className="flex flex-wrap gap-2">
              {fixed.map((a) => (
                <button key={a} onClick={() => setAmount(a)} aria-pressed={amount === a}
                  className={cn("rounded-xl px-3 py-2 text-sm font-bold transition", amount === a ? "bg-electric text-ink" : "bg-white/10 text-electric hover:bg-white/15")}>{money(a)}</button>
              ))}
            </div>
          </div>
        ) : (
          <p className="mt-4 text-center text-xs text-white/45">Minimum {money(min)} · Maximum {money(max)}</p>
        )}

        {boost && valid && amount > 0 && (() => {
          const cents = Math.round(amount * 100);
          const extra = Math.floor((cents * boost.percent + 50) / 100);  // same rounding as the server
          return (
            <div data-testid="boost-preview" className="mt-4 rounded-2xl border border-[#ffd966]/30 bg-[#ffd966]/10 p-3 text-sm">
              <p className="font-bold text-[#ffd966]">Deposit Boost +{boost.percent}% is active</p>
              <div className="mt-1.5 flex justify-between text-white/80"><span>To your wallet</span><span className="font-bold">{money(cents / 100)}</span></div>
              <div className="flex justify-between text-white/80"><span>Bonus balance</span><span className="font-bold text-[#ffd966]">+{money(extra / 100)}</span></div>
              <div className="mt-1 flex justify-between border-t border-white/10 pt-1.5 font-extrabold"><span>You receive</span><span>{money((cents + extra) / 100)}</span></div>
            </div>
          );
        })()}
        {error && <p role="alert" className="mt-4 rounded-2xl bg-red-500/15 p-3 text-sm text-red-200">{error}</p>}
        <p className="mt-4 text-xs text-white/45">You&apos;ll be sent to the payment page. Your balance is credited only after the payment is confirmed.</p>
        <div className="mt-5 grid grid-cols-[1.4fr_1fr] gap-3">
          <button onClick={submit} disabled={busy || !valid} className="inline-flex h-14 items-center justify-center gap-2 rounded-2xl bg-electric text-lg font-bold text-ink transition hover:brightness-110 disabled:opacity-50">
            {busy ? <Spinner /> : <ArrowDownToLine className="h-5 w-5" />}Continue
          </button>
          <button onClick={onBack} disabled={busy} className="h-14 rounded-2xl bg-white/5 text-lg font-bold text-white/80 hover:bg-white/10">Back</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function Cashout({ w, onDone }: { w: WalletState; onDone: () => void }) {
  const [method, setMethod] = useState<Method | null>(null);
  const [amount, setAmount] = useState("");
  const [address, setAddress] = useState("");
  const [chime, setChime] = useState("");
  const [busy, setBusy] = useState(false);
  const [showRules, setShowRules] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "err"; text: string } | null>(null);
  const attempt = useRef<{ k: string; key: string } | null>(null);

  if (w.withdrawal_methods.length === 0) return <p className="rounded-2xl bg-white/5 p-5 text-sm text-white/60">No cashout methods are available right now.</p>;

  const bal = Number(w.balance ?? 0), min = Number(w.cashout.min), max = Number(w.cashout.max);
  const amt = Number(amount);
  const cap = Math.min(max, bal);                           // can never withdraw more than the wallet holds
  const canCashOut = bal >= min;                            // exactly the minimum in the wallet is enough
  const amountOk = amt >= min && amt <= cap;

  const submit = async () => {
    if (!method) return;
    setBusy(true); setMsg(null);
    const k = `${method.id}:${amount}:${address}`;
    if (!attempt.current || attempt.current.k !== k) attempt.current = { k, key: crypto.randomUUID() };
    try {
      await api("/wallet/withdrawals", { method: "POST", body: { method_id: method.id, amount, address, chime_name: chime, idempotency_key: attempt.current.key } });
      attempt.current = null;
      setMsg({ tone: "ok", text: "Cashout requested. The amount is held and will be sent after review." });
      setAmount(""); setAddress(""); setChime("");
      onDone();
    } catch (e) { setMsg({ tone: "err", text: errorMessage(e) }); } finally { setBusy(false); }
  };

  return (
    <div>
      <div className="mb-4 flex flex-col gap-2">
        <div data-testid="cashout-min-notice" className={cn("rounded-2xl p-3.5 text-sm font-medium", canCashOut ? "bg-emerald-400/10 text-emerald-100 border border-emerald-400/20" : "bg-amber-300/10 text-amber-100 border border-amber-300/20")}>
          {canCashOut
            ? <>Minimum withdrawal is <b>{money(min)}</b>. You can withdraw up to <b>{money(cap)}</b> now.</>
            : <>Minimum withdrawal is <b>{money(min)}</b>. Your wallet has <b>{money(bal)}</b>; you need <b>{money(min - bal)}</b> more to withdraw.</>}
        </div>

        {w.cashout_rule && (
          <div className="flex items-center justify-between rounded-xl border border-white/5 bg-white/[0.03] px-3.5 py-2">
            <span className="text-xs text-white/60">Game cashout multiplier tiers:</span>
            <button
              type="button"
              onClick={() => setShowRules(true)}
              className="inline-flex items-center gap-1 text-xs font-bold text-electric hover:underline"
            >
              View Cashout Rules →
            </button>
          </div>
        )}
      </div>

      {showRules && <CashoutLimitsModal lead="Cashout" accent="Rules" confirmLabel="Close" onDone={() => setShowRules(false)} />}

      <div className="grid grid-cols-2 gap-3">
        {w.withdrawal_methods.map((m) => <Tile key={m.id} m={m} active={method?.id === m.id} onClick={() => { setMethod(m); setMsg(null); }} />)}
      </div>
      {method && (
        <div className="mt-5 space-y-3 rounded-2xl bg-white/5 p-4">
          <input className={inputCls} aria-label={w.payout_fields[method.value]} placeholder={`Your ${w.payout_fields[method.value]}`} value={address} onChange={(e) => setAddress(e.target.value)} autoComplete="off" />
          {method.value === "chime" && <input className={inputCls} aria-label="Name on Chime account" placeholder="Name on your Chime account" value={chime} onChange={(e) => setChime(e.target.value)} />}
          <input inputMode="decimal" className={inputCls} aria-label="Cashout amount in dollars" placeholder={`Amount (${money(w.cashout.min)} – ${money(cap >= min ? cap : w.cashout.max)})`} value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ""))} />
          {canCashOut && <button type="button" onClick={() => setAmount(cap.toFixed(2))} className="w-full rounded-xl bg-white/10 py-2 text-sm font-bold text-electric hover:bg-white/15">Withdraw everything ({money(cap)})</button>}
          {amount !== "" && !amountOk && <p role="alert" data-testid="cashout-amount-hint" className="text-sm text-amber-200">{amt < min ? `The minimum withdrawal is ${money(min)}.` : amt > bal ? `Your wallet only has ${money(bal)}.` : `The maximum per withdrawal is ${money(max)}.`}</p>}
          <button className={primaryBtn} onClick={submit} disabled={busy || !amountOk || !address || !canCashOut}>{busy ? <Spinner /> : <ArrowUpFromLine className="h-4 w-4" />}Cash out {amount && money(amount)}</button>
          <p className="text-xs text-white/45">Cashouts come from your wallet balance only (bonus balance cannot be withdrawn). They are reviewed before they are sent; you can cancel while a request is still in review.</p>
        </div>
      )}
      {msg && <p role={msg.tone === "err" ? "alert" : "status"} className={cn("mt-3 rounded-2xl p-3 text-sm", msg.tone === "err" ? "bg-red-500/15 text-red-200" : "bg-emerald-400/15 text-emerald-100")}>{msg.text}</p>}
    </div>
  );
}

function HistoryTab() {
  const [h, setH] = useState<History | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => { api<History>("/wallet/history").then(setH).catch((e) => setError(errorMessage(e))); }, []);
  useEffect(() => { load(); }, [load]);
  const cancel = async (id: number) => {
    try { await api(`/wallet/withdrawals/${id}/cancel`, { method: "POST" }); load(); notifyWalletChanged(); } catch (e) { setError(errorMessage(e)); }
  };
  if (error) return <p role="alert" className="rounded-2xl bg-red-500/15 p-3 text-sm text-red-200">{error}</p>;
  if (!h) return <div className="grid h-24 place-items-center"><Spinner /></div>;
  if (h.orders.length === 0 && h.ledger.length === 0) return <p className="rounded-2xl bg-white/5 p-5 text-sm text-white/60">No transactions yet.</p>;
  const tone = (s: string) => (["paid", "completed"].includes(s) ? "text-emerald-300" : ["failed", "rejected", "cancelled", "refunded"].includes(s) ? "text-red-300" : "text-amber-300");
  return (
    <div className="space-y-5">
      {h.orders.length > 0 && (
        <ul className="space-y-2">
          {h.orders.map((o) => (
            <li key={`${o.type}-${o.id}`} className="flex items-center justify-between gap-3 rounded-2xl bg-white/5 px-4 py-3 text-sm">
              <span><span className="font-bold capitalize">{o.type === "redeem" ? "Redeemed" : o.type}</span> · {o.method}{o.sandbox && <span className="ml-1 text-xs text-white/40">(sandbox)</span>}<span className="block text-xs text-white/45">{formatDate(o.created_at)}</span></span>
              <span className="text-right"><span className="block font-bold">{money(o.amount)}</span>{o.bonus && <span className="block text-xs font-semibold text-[#ffd966]">+{money(o.bonus)} bonus</span>}{o.voided && <span className="block text-xs font-semibold text-red-300">{money(o.voided)} voided</span>}<span className={cn("text-xs", tone(o.status))}>{STATUS_LABEL[o.status] ?? o.status}</span>
                {o.type === "cashout" && o.status === "pending_review" && <button onClick={() => cancel(o.id)} className="ml-2 text-xs font-semibold text-electric hover:underline">Cancel</button>}
                {o.type === "deposit" && o.status === "pending" && o.payment_url && <a href={o.payment_url} className="ml-2 text-xs font-semibold text-electric hover:underline">Pay now</a>}</span>
            </li>
          ))}
        </ul>
      )}
      {h.ledger.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-bold text-white/70">Balance changes</h3>
          <ul className="divide-y divide-white/10 text-sm">
            {h.ledger.map((e) => (
              <li key={e.id} className="flex justify-between py-2"><span>{KIND_LABEL[e.kind] ?? e.kind}{e.bucket === "bonus" && <span className="ml-1.5 rounded bg-[#ffd966]/15 px-1.5 py-0.5 text-[0.65rem] font-bold text-[#ffd966]">BONUS</span>}<span className="ml-2 text-xs text-white/40">{formatDate(e.created_at)}</span></span>
                <span className={Number(e.amount) >= 0 ? "text-emerald-300" : "text-white/80"}>{Number(e.amount) >= 0 ? "+" : ""}{money(e.amount)}</span></li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** Right-hand drawer: the wallet from anywhere on the site. Rendered through a portal on <body>: the sticky header has
 * backdrop-filter, which would otherwise make it the containing block of this fixed overlay and squash it. */
export function WalletDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !document.querySelector("[data-modal-nested]")) onClose(); };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = prev; };
  }, [open, onClose]);
  if (!open || typeof document === "undefined") return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex justify-end bg-ink/70 backdrop-blur-sm" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <aside role="dialog" aria-modal="true" aria-label="Wallet" className="h-full w-full max-w-md overflow-y-auto bg-[#111A32] p-6 text-white shadow-2xl">
        <div className="flex items-start justify-between">
          <div><h2 className="text-2xl font-extrabold">Wallet</h2><p className="mt-1 text-white/55">Deposit and cash out your funds in your wallet</p></div>
          <button onClick={onClose} aria-label="Close wallet" className="rounded-full p-1 text-white/60 hover:text-white"><X className="h-6 w-6" /></button>
        </div>
        <div className="mt-5"><WalletBody /></div>
      </aside>
    </div>,
    document.body,
  );
}
