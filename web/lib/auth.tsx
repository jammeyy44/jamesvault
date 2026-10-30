"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
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
  logout: () => Promise<void>;
};

const Ctx = createContext<AuthState>({
  player: null, loading: true, unread: 0, config: null, refresh: async () => {}, logout: async () => {},
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
    api<SiteConfig>("/site/config").then(setConfig).catch(() => {});
  }, [refresh]);

  const logout = useCallback(async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    setPlayer(null);
    setUnread(0);
  }, []);

  return <Ctx.Provider value={{ player, loading, unread, config, refresh, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
