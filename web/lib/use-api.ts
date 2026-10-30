"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "./api";

/**
 * Minimal data hook: { data, error, loading, reload }. Pass a null path to skip fetching.
 * `loading` is only true until the first result for a path arrives; reloads keep the current data
 * on screen so components don't unmount (and lose their local state) while refreshing.
 */
export function useApi<T = any>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const loadedPath = useRef<string | null>(null);

  const load = useCallback(async () => {
    if (path === null) return;
    if (loadedPath.current !== path) {
      setLoading(true);
      setData(null);
    }
    setError(null);
    try {
      setData(await api<T>(path));
      loadedPath.current = path;
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, error, loading, reload: load };
}
