import { Apple, CreditCard, Landmark } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Premium-looking method icons for the wallet. They are simple drawn glyphs in each method's colours (not the companies'
 * official logo files). Anything unknown gets a tasteful gradient tile with a generic icon.
 */
type Kind = "cashapp" | "chime" | "paypal" | "apple" | "google" | "card" | "venmo" | "bank" | "btc" | "eth" | "ltc" | "usdt" | "crypto" | "other";

function kindOf(value: string, name: string): Kind {
  const v = `${value} ${name}`.toLowerCase();
  if (/cash\s?app/.test(v)) return "cashapp";
  if (v.includes("chime")) return "chime";
  if (v.includes("paypal")) return "paypal";
  if (v.includes("apple")) return "apple";
  if (v.includes("google")) return "google";
  if (v.includes("venmo")) return "venmo";
  if (/bitcoin|\bbtc\b/.test(v)) return "btc";
  if (/ethereum|\beth\b/.test(v)) return "eth";
  if (/litecoin|\bltc\b/.test(v)) return "ltc";
  if (/usdt|tether/.test(v)) return "usdt";
  if (/crypto|coin/.test(v)) return "crypto";
  if (/card|visa|master/.test(v)) return "card";
  if (/bank|ach|wire/.test(v)) return "bank";
  return "other";
}

const RING = "ring-1 ring-white/20 shadow-[0_6px_16px_rgba(0,0,0,0.35)]";

function Coin({ bg, children, className }: { bg: string; children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("grid h-11 w-11 shrink-0 place-items-center rounded-full text-[1.15rem] font-black text-white", RING, className)} style={{ background: bg }} aria-hidden>
      {children}
    </span>
  );
}

export function PaymentIcon({ value, name, className }: { value: string; name: string; className?: string }) {
  const kind = kindOf(value, name);
  switch (kind) {
    case "cashapp":
      return <Coin bg="linear-gradient(145deg,#19E56A,#00B946)" className={className}><span className="-mt-px text-[1.5rem] leading-none">$</span></Coin>;
    case "chime":
      return <Coin bg="linear-gradient(145deg,#2BD98A,#12A864)" className={className}><span className="text-[1.45rem] leading-none" style={{ fontFamily: "Georgia, serif" }}>C</span></Coin>;
    case "paypal":
      return (
        <Coin bg="linear-gradient(145deg,#0B3FA8,#002A72)" className={className}>
          <span className="relative block h-6 w-6">
            <span className="absolute left-[3px] top-[1px] text-[1.45rem] font-black italic leading-none text-[#29A8E6]">P</span>
            <span className="absolute left-[7px] top-[3px] text-[1.45rem] font-black italic leading-none text-white">P</span>
          </span>
        </Coin>
      );
    case "apple":
      return <span className={cn("grid h-11 w-11 shrink-0 place-items-center rounded-full bg-white text-black", RING, className)} aria-hidden><Apple className="h-[22px] w-[22px] fill-current" strokeWidth={1.5} /></span>;
    case "google":
      return (
        <span className={cn("grid h-11 w-11 shrink-0 place-items-center rounded-full bg-white", RING, className)} aria-hidden>
          <span className="bg-[conic-gradient(from_-45deg,#EA4335_0deg_90deg,#FBBC05_90deg_180deg,#34A853_180deg_270deg,#4285F4_270deg_360deg)] bg-clip-text text-[1.6rem] font-black leading-none text-transparent" style={{ fontFamily: "Arial, sans-serif" }}>G</span>
        </span>
      );
    case "venmo":
      return <Coin bg="linear-gradient(145deg,#3D95CE,#1E6FB0)" className={className}><span className="text-[1.5rem] italic leading-none">V</span></Coin>;
    case "card":
      return <Coin bg="linear-gradient(145deg,#6D5EF5,#3B82F6)" className={className}><CreditCard className="h-[21px] w-[21px]" strokeWidth={2} /></Coin>;
    case "bank":
      return <Coin bg="linear-gradient(145deg,#475569,#1E293B)" className={className}><Landmark className="h-[20px] w-[20px]" strokeWidth={2} /></Coin>;
    case "btc":
      return <Coin bg="linear-gradient(145deg,#FFA928,#F7931A)" className={className}>₿</Coin>;
    case "eth":
      return <Coin bg="linear-gradient(145deg,#8A9CF0,#5C6BC0)" className={className}>Ξ</Coin>;
    case "ltc":
      return <Coin bg="linear-gradient(145deg,#C9CED6,#9AA3B2)" className={className}>Ł</Coin>;
    case "usdt":
      return <Coin bg="linear-gradient(145deg,#37B392,#1E9275)" className={className}>₮</Coin>;
    case "crypto":
      return (
        <span className={cn("flex shrink-0 items-center", className)} aria-hidden>
          <Coin bg="linear-gradient(145deg,#FFA928,#F7931A)">₿</Coin>
          <Coin bg="linear-gradient(145deg,#8A9CF0,#5C6BC0)" className="-ml-3">Ξ</Coin>
          <Coin bg="linear-gradient(145deg,#37B392,#1E9275)" className="-ml-3">₮</Coin>
        </span>
      );
    default: {
      // unknown method: a tidy gradient tile with the first letter, stable colour per method
      const hues = ["#2864F0", "#6D5EF5", "#16A34A", "#0EA5E9", "#9333EA", "#EA580C"];
      const color = hues[[...value].reduce((a, c) => a + c.charCodeAt(0), 0) % hues.length];
      return <Coin bg={`linear-gradient(145deg, ${color}, ${color}CC)`} className={className}>{name[0]}</Coin>;
    }
  }
}
