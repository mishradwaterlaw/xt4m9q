import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * src/hooks/useApi.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Single generic data-fetching hook for all API endpoints.
 *
 * Encapsulates:
 *   - Loading & error state transitions
 *   - Race-condition cancellation via AbortController
 *   - Per-hook in-memory caching keyed by params
 *   - Stable refetch mechanism via internal trigger counter
 */
export function useApi<T>(
  fetchFn: (...args: unknown[]) => Promise<T>,
  params: Record<string, unknown> = {},
  deps: unknown[] = []
): { data: T | null; isLoading: boolean; error: string | null; refetch: () => void } {
  const [data, setData] = useState<T | null>(null);
  // isLoading starts as true on first render so charts never flash an empty state
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [trigger, setTrigger] = useState<number>(0);

  // In-memory cache:
  // Cache is per-hook-instance (useRef Map), not global.
  // This is intentional: it scopes memory to the component's active lifecycle,
  // prevents unintended cross-component state collisions, allows automatic garbage
  // collection when the component unmounts, and avoids displaying stale data across sessions.
  const cacheRef = useRef<Map<string, T>>(new Map());

  const refetch = useCallback(() => {
    // Incrementing trigger forces the effect to rerun even if params/deps haven't changed
    setTrigger((c) => c + 1);
  }, []);

  useEffect(() => {
    const cacheKey = JSON.stringify(params ?? {});

    // Check if we already have valid data cached for these exact params
    const cached = cacheRef.current.get(cacheKey);
    if (cached !== undefined) {
      setData(cached);
      setIsLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    let isMounted = true;

    setIsLoading(true);
    setError(null);

    // Call fetchFn with params values (or signal directly if no params)
    const promise =
      params && Object.keys(params).length > 0
        ? fetchFn(...Object.values(params), controller.signal)
        : fetchFn(controller.signal);

    promise
      .then((result) => {
        if (!isMounted) return;
        cacheRef.current.set(cacheKey, result);
        setData(result);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
        // Distinguish AbortError from real failures:
        // AbortError is intentional cancellation from unmount or param change — silently ignore.
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        const message =
          err instanceof Error
            ? err.message
            : 'An unexpected error occurred while fetching data.';
        setError(message);
        setIsLoading(false);
      });

    return () => {
      isMounted = false;
      // cancels the in-flight request if the component unmounts or deps change before the response arrives, preventing stale data from overwriting a newer result
      controller.abort();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trigger, JSON.stringify(params), ...deps]);

  return { data, isLoading, error, refetch };
}
