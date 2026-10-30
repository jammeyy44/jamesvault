"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, Copy, Share2, UserPlus } from "lucide-react";
import { Badge, EmptyState, ErrorState, Notice, PageHeader, Skeleton } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { useApi } from "@/lib/use-api";
import { useAuth } from "@/lib/auth";
import { formatDay, referralLink } from "@/lib/utils";

type Referrals = {
  code: string;
  rules: string;
  bonus: string;
  counts: { pending: number; confirmed: number; rejected: number };
  items: { player: string; status: string; reward: string | null; created_at: string }[];
};

export default function ReferPage() {
  const { player, loading: authLoading } = useAuth();
  const { data, loading, error, reload } = useApi<Referrals>(player ? "/referrals/me" : null);
  const [copied, setCopied] = useState(false);

  const link = data ? referralLink(data.code) : "";
  const copy = async () => {
    try { await navigator.clipboard.writeText(link); } catch { /* clipboard blocked: the link is selectable in the box */ }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  const share = async () => {
    if (navigator.share) await navigator.share({ title: "Join me on stakesweep.net", text: "Join me on stakesweep.net with my link:", url: link }).catch(() => {});
    else copy();
  };

  return (
    <div className="container-x py-10">
      <PageHeader eyebrow="Refer a Friend" title="Invite friends, get rewarded">
        Share your personal link. When a friend who joins with it makes their first deposit, bonus balance is added to your account.
      </PageHeader>
      {authLoading ? (
        <Skeleton className="h-48" />
      ) : !player ? (
        <EmptyState title="Sign in to get your referral link" icon={<UserPlus className="h-6 w-6" />}>
          <div className="mt-3 flex justify-center gap-2">
            <Button asChild><Link href="/login">Log in</Link></Button>
            <Button asChild variant="secondary"><Link href="/register">Register</Link></Button>
          </div>
        </EmptyState>
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : loading || !data ? (
        <Skeleton className="h-64" />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
          <div className="space-y-6">
            <div className="surface p-6 sm:p-8">
              <p className="text-sm font-semibold text-muted">Your referral code</p>
              <p className="gradient-text mt-1 text-3xl font-black tracking-widest">{data.code}</p>
              <div className="mt-5 flex flex-col gap-2 sm:flex-row">
                <input readOnly value={link} className="field" aria-label="Referral link" onFocus={(e) => e.target.select()} />
                <Button onClick={copy} variant="secondary">
                  {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}{copied ? "Copied" : "Copy"}
                </Button>
                <Button onClick={share}><Share2 className="h-4 w-4" />Share</Button>
              </div>
            </div>
            <Notice>{data.rules}</Notice>
          </div>
          <div className="surface p-6">
            <div className="grid grid-cols-3 gap-3 text-center">
              {(["pending", "confirmed", "rejected"] as const).map((k) => (
                <div key={k} className="rounded-xl bg-soft p-3">
                  <p className="text-2xl font-extrabold">{data.counts[k]}</p>
                  <p className="text-xs text-muted">{k === "pending" ? "Signed up" : k === "confirmed" ? "Deposited" : "Rejected"}</p>
                </div>
              ))}
            </div>
            <h2 className="mb-2 mt-6 font-bold">Referral history</h2>
            {data.items.length === 0 ? (
              <p className="text-sm text-muted">No referrals yet. Share your link to get started.</p>
            ) : (
              <ul className="divide-y divide-line">
                {data.items.map((r, i) => (
                  <li key={i} className="flex items-center justify-between py-2.5 text-sm">
                    <span>{r.player}<span className="ml-2 text-xs text-muted">{formatDay(r.created_at)}</span></span>
                    {r.reward
                      ? <Badge tone="green">+${r.reward} bonus</Badge>
                      : <Badge tone={r.status === "rejected" || r.status === "reversed" ? "red" : "amber"}>{r.status === "pending" ? "Waiting for first deposit" : r.status === "reversed" ? "Bonus taken back (refund)" : r.status}</Badge>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
