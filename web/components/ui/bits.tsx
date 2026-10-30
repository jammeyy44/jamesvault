import * as React from "react";
import { cn } from "@/lib/utils";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";

export function Badge({ className, tone = "blue", ...props }: React.HTMLAttributes<HTMLSpanElement> & { tone?: "blue" | "green" | "amber" | "gray" | "red" }) {
  const tones = {
    blue: "bg-soft text-primary border-line",
    green: "bg-success/15 text-emerald-700 border-success/30",
    amber: "bg-amber-50 text-amber-700 border-amber-200",
    gray: "bg-slate-100 text-muted border-slate-200",
    red: "bg-red-50 text-red-700 border-red-200",
  };
  return <span className={cn("inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold", tones[tone], className)} {...props} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-xl bg-soft", className)} aria-hidden />;
}

export function EmptyState({ title, children, icon }: { title: string; children?: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div className="surface flex flex-col items-center gap-2 px-6 py-14 text-center">
      <div className="mb-1 grid h-12 w-12 place-items-center rounded-2xl bg-soft text-primary">{icon ?? <Inbox className="h-6 w-6" />}</div>
      <h3 className="text-lg font-semibold">{title}</h3>
      {children && <div className="max-w-md text-sm text-muted">{children}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="surface flex flex-col items-center gap-2 border-red-200 px-6 py-10 text-center">
      <AlertTriangle className="h-6 w-6 text-red-600" />
      <p className="text-sm text-ink">{message}</p>
      {onRetry && <button onClick={onRetry} className="text-sm font-semibold text-primary hover:underline">Try again</button>}
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-4 w-4 animate-spin", className)} aria-label="Loading" />;
}

export function Notice({ tone = "info", children }: { tone?: "info" | "error" | "success"; children: React.ReactNode }) {
  const tones = { info: "border-line bg-soft text-ink", error: "border-red-200 bg-red-50 text-red-800", success: "border-success/40 bg-success/10 text-emerald-900" };
  return <div role={tone === "error" ? "alert" : "status"} className={cn("rounded-xl border px-4 py-3 text-sm", tones[tone])}>{children}</div>;
}

export function PageHeader({ eyebrow, title, children }: { eyebrow?: string; title: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="mb-8 max-w-3xl">
      {eyebrow && <p className="mb-2 text-sm font-semibold uppercase tracking-wider text-primary">{eyebrow}</p>}
      <h1 className="text-3xl font-extrabold sm:text-4xl">{title}</h1>
      {children && <p className="mt-3 text-base text-muted">{children}</p>}
    </div>
  );
}

/** "Adding cash" + bouncing dots, for money buttons that are processing (pair with the btn-processing class). */
export function Processing({ label }: { label: string }) {
  return <span role="status" aria-live="polite" className="inline-flex items-center">{label}<span className="proc-dots" aria-hidden="true"><i /><i /><i /></span></span>;
}
