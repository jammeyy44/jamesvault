import Link from "next/link";
import { useState } from "react";
import { Heart, Play, Sparkles, Wrench } from "lucide-react";
import type { Game } from "@/lib/api";
import { cn } from "@/lib/utils";

type Props = {
  game: Game;
  onFavorite?: (game: Game) => void;
  onPlay?: (game: Game) => void;
};

const DEFAULT_COVERS = [
  "/images/game_royal_vault.webp",
  "/images/game_estar.webp",
  "/images/game_royal_treasure.webp",
  "/images/game_yolo_wheel.webp",
  "/images/game_vblink.webp",
];

function getCover(game: Game) {
  if (game.image_url) return game.image_url;
  const idx = Math.abs(game.name.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0)) % DEFAULT_COVERS.length;
  return DEFAULT_COVERS[idx];
}

export function GameCard({ game, onFavorite, onPlay }: Props) {
  const [broken, setBroken] = useState(false);
  const maintenance = game.status === "maintenance";
  const coverUrl = broken ? DEFAULT_COVERS[0] : getCover(game);

  return (
    <Link
      href={`/game/${game.slug}`}
      prefetch={true}
      onClick={(e) => {
        if (maintenance) e.preventDefault();
        onPlay?.(game);
      }}
      className="group relative block overflow-hidden rounded-2xl sm:rounded-[1.4rem] border border-white/10 bg-[#131927] shadow-card transition-all duration-300 hover:-translate-y-1 hover:border-sky-400/70 hover:shadow-[0_12px_30px_rgba(56,189,248,0.3)]">
      
      {/* Full-bleed poster image container with 3:4 aspect ratio matching reference image 2 */}
      <div className="relative aspect-[3/4] w-full overflow-hidden bg-slate-900">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={coverUrl}
          alt={game.name}
          loading="lazy"
          onError={() => setBroken(true)}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
        />

        {/* Top badges */}
        <div className="absolute left-2.5 top-2.5 flex items-center gap-1 z-10">
          {game.is_new && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/90 px-2 py-0.5 text-[10px] font-extrabold text-white shadow-sm backdrop-blur-sm">
              <Sparkles className="h-2.5 w-2.5" /> NEW
            </span>
          )}
          {maintenance && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/90 px-2 py-0.5 text-[10px] font-extrabold text-white shadow-sm backdrop-blur-sm">
              <Wrench className="h-2.5 w-2.5" /> Maintenance
            </span>
          )}
        </div>

        {/* Favorite heart button at top right */}
        {onFavorite && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onFavorite(game);
            }}
            aria-pressed={!!game.favorite}
            aria-label={game.favorite ? `Remove ${game.name} from favorites` : `Add ${game.name} to favorites`}
            className="absolute right-2.5 top-2.5 z-10 grid h-8 w-8 place-items-center rounded-full bg-black/40 text-white backdrop-blur-md border border-white/10 transition-all hover:scale-110 hover:bg-black/60">
            <Heart className={cn("h-4 w-4 transition-colors", game.favorite ? "fill-rose-500 text-rose-500" : "text-white/80")} />
          </button>
        )}

        {/* Center play icon overlay appearing on hover */}
        <div className="absolute inset-0 grid place-items-center opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-10 pointer-events-none bg-black/25 backdrop-blur-[2px]">
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-sky-400 text-slate-950 font-black shadow-[0_4px_25px_rgba(56,189,248,0.7)] transform scale-90 group-hover:scale-100 transition-transform duration-300">
            <Play className="h-5 w-5 fill-current ml-0.5" />
          </span>
        </div>

        {/* Bottom dark vignette overlay with title matching reference image 2 */}
        <div className="absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/95 via-black/50 to-transparent pt-12 pb-3.5 px-3.5">
          <h3 className="text-sm xs:text-base sm:text-lg font-black text-white leading-tight tracking-tight drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)] truncate">
            {game.name}
          </h3>
          <p className="text-[11px] font-bold text-sky-400/90 truncate mt-0.5">
            {game.category || "Slots"}
          </p>
        </div>
      </div>
    </Link>
  );
}
