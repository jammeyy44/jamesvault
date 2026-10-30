import type { Metadata } from "next";
import { BonusZone } from "@/components/bonus-zone";

export const metadata: Metadata = {
  title: "Bonus Zone",
  description: "Earn diamonds with simple tasks and exchange them for free play and bonuses in the Lucky Shop.",
  alternates: { canonical: "/bonus-zone" },
};

export default function BonusZonePage() {
  return <BonusZone />;
}
