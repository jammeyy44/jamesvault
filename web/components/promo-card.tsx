"use client";

import { useState } from "react";
import { Check, Gift, Tag } from "lucide-react";
import { Badge, Notice } from "./ui/bits";
import { Button } from "./ui/button";
import { api, errorMessage, type Promotion } from "@/lib/api";
import { formatDay } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import Link from "next/link";

export function PromoCard({ promo, onChanged }: { promo: Promotion; onChanged?: () => void }) {
  const { player } = useAuth();
  const [open, setOpen] = useState(false);
  const [coupon, setCoupon] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "error" | "success"; text: string } | null>(null);

  const claim = async () => {
    setBusy(true); setMsg(null);
    try {
      await api(`/promotions/${promo.slug}/claim`, { method: "POST", body: { coupon } });
      setMsg({ tone: "success", text: "Claim received. Our team will confirm it; you'll see an update in your notifications." });
      onChanged?.();
    } catch (e) {
      setMsg({ tone: "error", text: errorMessage(e) });
    } finally { setBusy(false); }
  };

  return (
    <article className="flex flex-col overflow-hidden rounded-xl2 border border-line bg-white shadow-card transition hover:shadow-lift">
      <div className="relative h-36 bg-gradient-to-br from-[#1B2A5C] via-[#26308A] to-violet">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {promo.image_url && <img src={promo.image_url} alt="" loading="lazy" className="h-full w-full object-cover" />}
        <div className="absolute inset-0 grid place-items-center text-white/20"><Gift className="h-16 w-16" /></div>
        <div className="absolute left-4 top-4 flex gap-2">
          <Badge tone={promo.state === "live" ? "green" : "amber"} className="bg-white">{promo.state === "live" ? "Live" : "Coming soon"}</Badge>
          <Badge tone="blue" className="bg-white capitalize">{promo.promo_type.replace("_", " ")}</Badge>
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-5">
        <h3 className="text-lg font-bold">{promo.title}</h3>
        {promo.description && <p className="text-sm text-muted">{promo.description}</p>}
        <dl className="space-y-1.5 text-sm">
          {promo.reward_details && <Row k="Reward" v={promo.reward_details} />}
          {promo.eligibility && <Row k="Eligibility" v={promo.eligibility} />}
          {(promo.starts_at || promo.ends_at) && (
            <Row k="Dates" v={`${promo.starts_at ? formatDay(promo.starts_at) : "Now"} – ${promo.ends_at ? formatDay(promo.ends_at) : "Open-ended"}`} />
          )}
        </dl>
        {promo.terms && (
          <div>
            <button className="text-sm font-semibold text-primary hover:underline" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
              {open ? "Hide terms" : "Terms & conditions"}
            </button>
            {open && <p className="mt-2 whitespace-pre-line rounded-xl bg-soft p-3 text-xs text-muted">{promo.terms}</p>}
          </div>
        )}
        <div className="mt-auto space-y-3 pt-2">
          {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
          {promo.can_claim && promo.requires_coupon && (
            <div className="relative">
              <Tag className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
              <input className="field pl-9" placeholder="Coupon code" value={coupon} onChange={(e) => setCoupon(e.target.value)} aria-label="Coupon code" />
            </div>
          )}
          {promo.claimed ? (
            <Button variant="secondary" disabled className="w-full"><Check className="h-4 w-4" /> {promo.claim_blocked_reason ?? "Claimed"}</Button>
          ) : promo.can_claim ? (
            <Button className="w-full" onClick={claim} disabled={busy || (promo.requires_coupon && !coupon.trim())}>Claim reward</Button>
          ) : !player && promo.state === "live" ? (
            <Button asChild className="w-full"><Link href="/login">Sign in to claim</Link></Button>
          ) : (
            <Button variant="secondary" disabled className="w-full">{promo.claim_blocked_reason ?? "Unavailable"}</Button>
          )}
        </div>
      </div>
    </article>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return <div className="flex gap-2"><dt className="w-20 shrink-0 font-semibold">{k}</dt><dd className="text-muted">{v}</dd></div>;
}
