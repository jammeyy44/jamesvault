"use client";

import { useEffect, useState } from "react";
import { api, errorMessage } from "./api";

/**
 * Stale-while-revalidate cache for data that rarely changes (cashout rules, site settings, game lists, payment options).
 * A saved copy is shown instantly (memory first, then this device's storage), and a fresh copy is fetched in the background
 * once it is older than `ttlMs`. Balances and anything money-critical are NOT cached here: the server stays the source of truth.
 */
type Entry = { at: number; data: unknown };
const PREFIX = "jv-cache:";
const memory = new Map<string, Entry>();
const inflight = new Map<string, Promise<unknown>>();

function readStored(key: string): Entry | null {
  try { const raw = localStorage.getItem(PREFIX + key); return raw ? (JSON.parse(raw) as Entry) : null; } catch { return null; }
}
function writeStored(key: string, e: Entry) {
  try { localStorage.setItem(PREFIX + key, JSON.stringify(e)); } catch { /* storage full or blocked: memory still works */ }
}

/** The saved copy (any age), or null. Call it in effects/handlers only (it reads browser storage). */
export function peekCached<T>(path: string, persist = true): T | null {
  const e = memory.get(path) ?? (persist ? readStored(path) : null);
  if (e) memory.set(path, e);
  return e ? (e.data as T) : null;
}

function fetchFresh<T>(path: string, persist: boolean): Promise<T> {
  const running = inflight.get(path);
  if (running) return running as Promise<T>;
  const p = api<T>(path)
    .then((data) => { const e = { at: Date.now(), data }; memory.set(path, e); if (persist) writeStored(path, e); return data; })
    .finally(() => inflight.delete(path));
  inflight.set(path, p);
  return p;
}

/** Resolves with a copy younger than ttlMs straight from the cache, otherwise fetches (one request even if many ask at once). */
export function cachedApi<T>(path: string, ttlMs: number, persist = true): Promise<T> {
  const e = memory.get(path) ?? (persist ? readStored(path) : null);
  if (e && Date.now() - e.at < ttlMs) { memory.set(path, e); return Promise.resolve(e.data as T); }
  return fetchFresh<T>(path, persist);
}

/** Hook form: shows the saved copy at once, then the fresh one. */
export function useCachedApi<T>(path: string | null, ttlMs: number, persist = true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!path) return;
    let live = true;
    const saved = peekCached<T>(path, persist);
    if (saved) setData(saved);
    cachedApi<T>(path, ttlMs, persist).then((d) => { if (live) { setData(d); setError(null); } })
      .catch((e) => { if (live && !saved) setError(errorMessage(e)); });
    return () => { live = false; };
  }, [path, ttlMs, persist]);
  return { data, error, loading: data === null && error === null };
}

/** A saved value under any key (this device), and saving one. */
export const readSaved = <T,>(key: string): T | null => { const e = memory.get(key) ?? readStored(key); if (e) memory.set(key, e); return e ? (e.data as T) : null; };
export const save = (key: string, data: unknown) => { const e = { at: Date.now(), data }; memory.set(key, e); writeStored(key, e); };

// ---------------------------------------------------------------- per-player memory (cleared when they sign out)
const userMemory = new Map<string, unknown>();
export const getUserCached = <T,>(key: string) => (userMemory.get(key) as T | undefined) ?? null;
export const setUserCached = (key: string, value: unknown) => { userMemory.set(key, value); };
export const clearUserCache = () => { userMemory.clear(); };

export const MINUTE = 60_000;
