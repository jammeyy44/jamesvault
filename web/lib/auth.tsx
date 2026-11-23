"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { MINUTE, cachedApi, peekCached } from "./cache";
import { api, type Player } from "./api";

type SiteConfig = {
  brand: { name: string; tagline: string; support_email: string; min_age: number };
  features: { wallet: boolean; game_launch: boolean; reward_wheel: boolean; registration: boolean };
};

type AuthState = {
  player: Player | null;
  loading: boolean;
  unread: number;
  config: SiteConfig | null;
  refresh: () => Promise<void>;
  /** Use the player the sign-in / sign-up answer already returned: no extra round trip before moving on. */
  signedIn: (p: Player) => void;
  logout: () => Promise<void>;
};

const Ctx = createContext<AuthState>({
  player: null, loading: true, unread: 0, config: null, refresh: async () => {}, signedIn: () => {}, logout: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [player, setPlayer] = useState<Player | null>(null);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState<SiteConfig | null>(null);

  const refresh = useCallback(async () => {
    try {
      const me = await api<{ player: Player | null; unread_notifications?: number }>("/auth/me");
      setPlayer(me.player);
      setUnread(me.unread_notifications ?? 0);
    } catch {
      setPlayer(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const saved = peekCached<SiteConfig>("/site/config");
    if (saved) setConfig(saved);
    cachedApi<SiteConfig>("/site/config", 10 * MINUTE).then(setConfig).catch(() => {});
  }, [refresh]);

  const signedIn = useCallback((p: Player) => { setPlayer(p); setLoading(false); }, []);

  const logout = useCallback(async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    setPlayer(null);
    setUnread(0);
  }, []);

  return <Ctx.Provider value={{ player, loading, unread, config, refresh, signedIn, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
