import type { Metadata } from "next";
import { GameGrid } from "@/components/game-grid";
import { PageHeader } from "@/components/ui/bits";

export const metadata: Metadata = {
  title: "Games",
  description: "Browse and search the game lobby by provider and category.",
  alternates: { canonical: "/games" },
};

export default function GamesPage() {
  return (
    <div className="container-x py-10">
      <PageHeader eyebrow="Game lobby" title="Find your next game">
        Search the catalog, filter by provider or category and save favorites to your account.
      </PageHeader>
      <GameGrid limit={24} />
    </div>
  );
}
