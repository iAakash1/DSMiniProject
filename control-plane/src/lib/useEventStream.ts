"use client";

import { useEffect, useRef, useState } from "react";
import { controlApiBaseUrl, fetchJson, type ProtocolEventRow } from "@/lib/controlApi";

export interface EventStreamState {
  events: ProtocolEventRow[];
  streaming: boolean;
  usingFallbackPolling: boolean;
}

function parseEventOrNull(raw: string): ProtocolEventRow | null {
  try {
    return JSON.parse(raw) as ProtocolEventRow;
  } catch {
    return null;
  }
}

export function useEventStream(maxEvents: number = 300): EventStreamState {
  const [events, setEvents] = useState<ProtocolEventRow[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [usingFallbackPolling, setUsingFallbackPolling] = useState(false);
  const eventsRef = useRef<ProtocolEventRow[]>([]);

  useEffect(() => {
    let cancelled = false;
    let source: EventSource | null = null;
    let fallbackTimer: ReturnType<typeof setInterval> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function pushEvent(event: ProtocolEventRow) {
      eventsRef.current = [event, ...eventsRef.current].slice(0, maxEvents);
      setEvents(eventsRef.current);
    }

    async function startFallbackPolling() {
      if (fallbackTimer) return;
      setUsingFallbackPolling(true);
      fallbackTimer = setInterval(() => {
        fetchJson<{ events: ProtocolEventRow[] }>("/events?limit=100")
          .then((payload) => {
            if (!cancelled) {
              eventsRef.current = payload.events;
              setEvents(payload.events);
            }
          })
          .catch(() => undefined);
      }, 4000);
    }

    function connect() {
      if (cancelled) return;
      source = new EventSource(`${controlApiBaseUrl()}/events/stream`);
      source.onopen = () => {
        setStreaming(true);
        setUsingFallbackPolling(false);
        if (fallbackTimer) {
          clearInterval(fallbackTimer);
          fallbackTimer = null;
        }
      };
      source.onmessage = (message) => {
        const parsed = parseEventOrNull(message.data);
        if (parsed) {
          pushEvent(parsed);
        }
      };
      source.onerror = () => {
        setStreaming(false);
        source?.close();
        startFallbackPolling();
        reconnectTimer = setTimeout(connect, 5000);
      };
    }

    connect();
    return () => {
      cancelled = true;
      source?.close();
      if (fallbackTimer) clearInterval(fallbackTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, [maxEvents]);

  return { events, streaming, usingFallbackPolling };
}
