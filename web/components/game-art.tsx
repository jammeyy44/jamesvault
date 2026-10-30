"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

/** A tidy colour per game name, so tiles of different games look different (never borrowed artwork from another game). */
function gradient(seed: string) {
  let h = 0;
  for (const c of seed) h = (h * 31 + c.charCodeAt(0)) % 360;
  return `linear-gradient(145deg, hsl(${(h % 40) + 235} 62% 24%) 0%, hsl(${(h % 50) + 255} 66% 42%) 100%)`;
}

const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";

/**
 * The game's own thumbnail (uploaded in Admin -> Game catalog). Until one is uploaded, or if it fails to load, a neutral tile
 * with the game's initials is shown: we never show some other game's artwork in its place.
 */
export function GameArt({ game, className, label = false }: { game: { name: string; image_url: string | null }; className?: string; label?: boolean }) {
  const [broken, setBroken] = useState(false);
  const showImage = !!game.image_url && !broken;
  return (
    <div className={cn("relative overflow-hidden", className)} style={showImage ? undefined : { background: gradient(game.name) }}>
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={game.image_url!} alt={game.name} loading="lazy" decoding="async" onError={() => setBroken(true)} className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" />
      ) : (
        <div className="absolute inset-0 grid place-items-center" aria-label={game.name} role="img">
          <span className="select-none font-black tracking-wide text-white/90" style={{ fontSize: "clamp(0.9rem, 28cqmin, 3.5rem)" }}>{initials(game.name)}</span>
          {label && <span className="absolute inset-x-3 bottom-4 truncate text-center text-xs font-semibold text-white/60">{game.name}</span>}
        </div>
      )}
    </div>
  );
}
