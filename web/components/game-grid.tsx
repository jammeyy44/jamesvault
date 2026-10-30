"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Heart, Search, Gamepad2, X } from "lucide-react";
import { GameCard } from "./game-card";
import { GameAccessModal } from "./game-access";
import { EmptyState, ErrorState, Notice, Skeleton } from "./ui/bits";
import { Button } from "./ui/button";
import { api, errorMessage, type Game } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Result = {
  items: Game[]; total: number; page: number; per_page: number;
  providers: { id: number; name: string }[]; categories: string[];
};

export function GameGrid({ featuredOnly = false, limit = 12, compact = false }: { featuredOnly?: boolean; limit?: number; compact?: boolean }) {
  const router = useRouter();
  const { player } = useAuth();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState("");
  const [category, setCategory] = useState("");
  const [favorites, setFavorites] = useState(false);
  const [newOnly, setNewOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Game[]>([]);
  const [meta, setMeta] = useState<Pick<Result, "total" | "providers" | "categories">>({ total: 0, providers: [], categories: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ tone: "info" | "error"; text: string } | null>(null);
  const [active, setActive] = useState<Game | null>(null);

  useEffect(() => { const t = setTimeout(() => { setQuery(search); setPage(1); }, 300); return () => clearTimeout(t); }, [search]);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    const qs = new URLSearchParams({ page: String(page), per_page: String(limit) });
    if (query) qs.set("search", query);
    if (provider) qs.set("provider", provider);
    if (category) qs.set("category", category);
    if (featuredOnly) qs.set("featured", "1");
    if (favorites) qs.set("favorites", "1");
    if (newOnly) qs.set("new", "1");
    try {
      const r = await api<Result>(`/games?${qs}`);
      setItems((prev) => (page === 1 ? r.items : [...prev, ...r.items]));
      setMeta({ total: r.total, providers: r.providers, categories: r.categories });
    } catch (e) { setError(errorMessage(e)); } finally { setLoading(false); }
  }, [page, query, provider, category, featuredOnly, favorites, newOnly, limit, player?.id]);

  useEffect(() => { load(); }, [load]);

  const reset = (fn: () => void) => { fn(); setPage(1); };

  const toggleFavorite = async (game: Game) => {
    if (!player) { router.push("/login"); return; }
    const next = !game.favorite;
    setItems((list) => list.map((g) => (g.id === game.id ? { ...g, favorite: next } : g)));
    try { await api(`/favorites/${game.slug}`, { method: next ? "PUT" : "DELETE" }); }
    catch (e) {
      setItems((list) => list.map((g) => (g.id === game.id ? { ...g, favorite: !next } : g)));
      setToast({ tone: "error", text: errorMessage(e) });
    }
  };

  // "Play" navigates directly to the full-screen game page instantly
  const play = (game: Game) => {
    setToast(null);
    router.push(`/game/${game.slug}`);
  };

  const showFilters = !featuredOnly && !compact;
  const hasFilters = !!(query || provider || category || favorites || newOnly);

  return (
    <div>
      {showFilters && (
        <div className="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Sleek Search Pill */}
          <div className="relative w-full md:max-w-xs">
            <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              className="w-full rounded-2xl border border-white/10 bg-[#131927]/90 pl-10 pr-9 py-2.5 text-sm text-white placeholder:text-slate-500 backdrop-blur-md transition focus:border-sky-400/50 focus:outline-none focus:ring-2 focus:ring-sky-400/20"
              placeholder="Search games..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search games"
            />
            {search && (
              <button
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                onClick={() => setSearch("")}
                aria-label="Clear search"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Category & Status Pills */}
          <div className="flex items-center gap-2 overflow-x-auto py-1.5 px-0.5 scrollbar-none max-w-full">
            <Chip active={!category && !newOnly && !favorites} onClick={() => reset(() => { setCategory(""); setNewOnly(false); setFavorites(false); })}>
              All Games
            </Chip>
            {meta.categories
              .filter((c) => !/^\d+$/.test(c.trim()))
              .map((c) => (
                <Chip key={c} active={category === c} onClick={() => reset(() => setCategory(category === c ? "" : c))}>
                  {c}
                </Chip>
              ))}
            <Chip active={newOnly} onClick={() => reset(() => setNewOnly(!newOnly))}>
              ✨ New
            </Chip>
            {player && (
              <Chip active={favorites} onClick={() => reset(() => setFavorites(!favorites))}>
                <Heart className="h-3.5 w-3.5 fill-current text-rose-400" /> Favorites
              </Chip>
            )}
            {hasFilters && (
              <button
                className="ml-1 text-xs font-bold text-sky-400 hover:text-sky-300 transition whitespace-nowrap px-2.5 py-1.5 rounded-lg hover:bg-white/5"
                onClick={() => { setSearch(""); setProvider(""); setCategory(""); setFavorites(false); setNewOnly(false); setPage(1); }}
              >
                Reset
              </button>
            )}
          </div>
        </div>
      )}

      {toast && <div className="mb-4"><Notice tone={toast.tone}>{toast.text}</Notice></div>}

      {error ? (
        <ErrorState message={error} onRetry={load} />
      ) : loading && items.length === 0 ? (
        <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: Math.min(limit, 8) }).map((_, i) => (
            <div key={i} className="aspect-[3/4] rounded-2xl bg-white/5 animate-pulse border border-white/10" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState title={hasFilters ? "No games match your filters" : "No games listed yet"} icon={<Gamepad2 className="h-6 w-6" />}>
          {hasFilters ? "Try a different search or clear the filters." : "Games appear here as soon as they are added to the catalog."}
        </EmptyState>
      ) : (
        <>
          <p className="mb-3 text-xs sm:text-sm text-slate-400 font-medium" aria-live="polite">
            {meta.total} {meta.total === 1 ? "game" : "games"} available
          </p>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
            {items.map((g) => <GameCard key={g.id} game={g} onFavorite={toggleFavorite} onPlay={play} />)}
          </div>
          {items.length < meta.total && !featuredOnly && !compact && (
            <div className="mt-8 flex justify-center">
              <Button variant="secondary" className="border-white/10 bg-[#131927] text-white hover:bg-white/10" onClick={() => setPage((p) => p + 1)} disabled={loading}>
                {loading ? "Loading…" : "Load more games"}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-xl border px-3.5 py-2 text-xs sm:text-sm font-bold transition-all duration-200 select-none",
        active
          ? "border-violet-400/40 bg-gradient-to-r from-[#7c3aed] to-[#4f46e5] text-white shadow-[0_0_15px_rgba(124,58,237,0.45)] ring-1 ring-violet-400/30"
          : "border-white/10 bg-[#121827]/90 text-slate-300 hover:border-white/25 hover:bg-[#1a2236] hover:text-white backdrop-blur-md"
      )}
    >
      {children}
    </button>
  );
}
