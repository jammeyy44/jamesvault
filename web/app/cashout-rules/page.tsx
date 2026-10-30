"use client";

import { Skeleton, ErrorState } from "@/components/ui/bits";
import { useApi } from "@/lib/use-api";

type Rules = {
  table: { deposit: string; min: string; max: string }[]; note: string;
  bonus: { table: { made: string; wallet: string }[]; note: string; min: string };
  facts: { min_deposit: string; max_redeem: string; min_wallet_cashout: string };
};

export default function CashoutRulesPage() {
  const { data, error, loading } = useApi<Rules>("/cashout-rules");
  return (
    <div className="container-x max-w-3xl py-10">
      <h1 className="text-3xl font-extrabold">Cashout rules</h1>
      <p className="mt-2 text-sm text-muted">How cashing out of a game works, and what you can take out.</p>
      {loading ? <Skeleton className="mt-8 h-64" /> : error || !data ? <ErrorState message={error ?? "Could not load the rules."} /> : (
        <div className="mt-8 space-y-6">
          <section className="surface p-6">
            <h2 className="font-bold">How it works</h2>
            <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-sm text-muted">
              <li>Add cash to a game (from your wallet or your bonus balance) and play.</li>
              <li>The <b className="text-ink">latest cash you added to that game</b> sets your cashout range: a minimum and a maximum (table below). Bonus added to the game does not count towards the range, and adding under {data.facts.min_deposit} does not unlock cashing out.</li>
              <li>Press Cash Out in the game. Your whole game balance leaves the game and the allowed amount is added to your <b className="text-ink">wallet</b>. Anything above the maximum is voided, and you confirm that first.</li>
              <li>One cash out per cash added. To cash out again, add cash to the game again.</li>
              <li>Wallet cashouts to your payout method start at {data.facts.min_wallet_cashout}.</li>
            </ol>
          </section>
          <section className="surface overflow-x-auto p-6">
            <h2 className="font-bold">Cashout limits by cash added</h2>
            <table className="mt-3 w-full text-left text-sm">
              <thead><tr className="border-b border-line text-xs uppercase tracking-wide text-muted"><th className="py-2 pr-4">Cash added</th><th className="py-2 pr-4">Minimum</th><th className="py-2">Maximum</th></tr></thead>
              <tbody className="divide-y divide-line">{data.table.map((r) => <tr key={r.deposit}><td className="py-2 pr-4 font-semibold">{r.deposit}</td><td className="py-2 pr-4">{r.min}</td><td className="py-2">{r.max}</td></tr>)}</tbody>
            </table>
            <p className="mt-3 text-xs text-muted">x3 / x12 mean 3 / 12 times the cash you added. {data.note}</p>
          </section>
          <section className="surface p-6">
            <h2 className="font-bold">Bonus-only games</h2>
            <p className="mt-2 text-sm text-muted">Bonus can only be added to a game, never withdrawn directly. If a game was funded <b className="text-ink">only by bonus</b> (no cash of your own added), the game balance must reach <b className="text-ink">{data.bonus.min}</b> to cash out, and your wallet is credited a fixed amount:</p>
            <table className="mt-3 w-full text-left text-sm">
              <thead><tr className="border-b border-line text-xs uppercase tracking-wide text-muted"><th className="py-2 pr-4">Game balance made</th><th className="py-2">Credited to wallet</th></tr></thead>
              <tbody className="divide-y divide-line">{data.bonus.table.map((r) => <tr key={r.made}><td className="py-2 pr-4 font-semibold">{r.made}</td><td className="py-2">{r.wallet}</td></tr>)}</tbody>
            </table>
            <p className="mt-3 text-xs text-muted">{data.bonus.note} If you add your own cash to the game, the cash table above applies instead.</p>
          </section>
        </div>
      )}
    </div>
  );
}
