import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";

/**
 * GET an endpoint and keep the result in state. Pass `null` as the path to skip the request.
 * Refetches when the path, params or `deps` change, or when `reload()` is called.
 */
export function useApi<T = any>(path: string | null, params?: Record<string, unknown>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);
  const paramsKey = JSON.stringify(params ?? {});

  useEffect(() => {
    if (!path) return;
    let live = true;
    setLoading(true);
    setError(null);
    api.get<T>(path, params)
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, paramsKey, tick, ...deps]);

  return { data, error, loading, reload: () => setTick((t) => t + 1) };
}
