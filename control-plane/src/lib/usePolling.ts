"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface PollingState<DataType> {
  data: DataType | null;
  loading: boolean;
  error: string | null;
  lastUpdatedAt: Date | null;
  connected: boolean;
  reload: () => void;
}

export function usePolling<DataType>(
  fetcher: () => Promise<DataType>,
  intervalMs: number = 4000,
): PollingState<DataType> {
  const [data, setData] = useState<DataType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const [connected, setConnected] = useState(false);
  const fetcherRef = useRef(fetcher);
  const tickRef = useRef<() => void>(() => {});
  const requestIdRef = useRef(0);

  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function tick() {
      const requestId = ++requestIdRef.current;
      try {
        const result = await fetcherRef.current();
        if (cancelled || requestId !== requestIdRef.current) return;
        setData(result);
        setError(null);
        setConnected(true);
        setLastUpdatedAt(new Date());
      } catch (caught) {
        if (cancelled || requestId !== requestIdRef.current) return;
        setConnected(false);
        setError(caught instanceof Error ? caught.message : "request failed");
      } finally {
        if (!cancelled && requestId === requestIdRef.current) {
          setLoading(false);
          timer = setTimeout(tick, intervalMs);
        }
      }
    }

    tickRef.current = () => {
      clearTimeout(timer);
      tick();
    };

    tick();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [intervalMs]);

  const reload = useCallback(() => {
    tickRef.current();
  }, []);

  return { data, loading, error, lastUpdatedAt, connected, reload };
}
