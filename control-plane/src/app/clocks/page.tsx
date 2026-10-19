"use client";

import { useMemo, useState } from "react";
import { Header } from "@/components/Header";
import { EmptyState } from "@/components/StateViews";
import { useEventStream } from "@/lib/useEventStream";

export default function ClocksPage() {
  const { events, streaming, usingFallbackPolling } = useEventStream();
  const [processFilter, setProcessFilter] = useState("");
  const [eventTypeFilter, setEventTypeFilter] = useState("");
  const [runFilter, setRunFilter] = useState("");

  const processOptions = useMemo(() => Array.from(new Set(events.map((event) => event.process_id))).sort(), [events]);
  const eventTypeOptions = useMemo(() => Array.from(new Set(events.map((event) => event.event_type))).sort(), [events]);

  const filtered = events.filter((event) => {
    if (processFilter && event.process_id !== processFilter) return false;
    if (eventTypeFilter && event.event_type !== eventTypeFilter) return false;
    if (runFilter && event.run_id !== runFilter) return false;
    return true;
  });

  return (
    <div>
      <Header
        title="Lamport clock explorer"
        subtitle={
          <>
            Each row is one causal event from one process&apos;s own logical clock. Lamport order proves causality
            only between events actually connected by a message — it does not prove two arbitrary rows are
            concurrent or not.{" "}
            <span className="connection-pill">
              <span className={`connection-dot ${streaming ? "live" : usingFallbackPolling ? "stale" : ""}`} />
              {streaming ? "streaming via SSE" : usingFallbackPolling ? "polling fallback (stream disconnected)" : "connecting…"}
            </span>
          </>
        }
      />

      <div className="toolbar">
        <select value={processFilter} onChange={(event) => setProcessFilter(event.target.value)}>
          <option value="">All processes</option>
          {processOptions.map((process) => (
            <option key={process} value={process}>
              {process}
            </option>
          ))}
        </select>
        <select value={eventTypeFilter} onChange={(event) => setEventTypeFilter(event.target.value)}>
          <option value="">All event types</option>
          {eventTypeOptions.map((eventType) => (
            <option key={eventType} value={eventType}>
              {eventType}
            </option>
          ))}
        </select>
        <input placeholder="Run ID" value={runFilter} onChange={(event) => setRunFilter(event.target.value)} />
      </div>

      {filtered.length === 0 ? (
        <EmptyState message="No matching events yet." />
      ) : (
        <table>
          <thead>
            <tr>
              <th>Process</th>
              <th>Role</th>
              <th>Event</th>
              <th>Lamport</th>
              <th>Wall clock</th>
              <th>Run</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((event) => (
              <tr key={event.id}>
                <td className="mono">{event.process_id}</td>
                <td>{event.process_role}</td>
                <td>{event.event_type}</td>
                <td className="mono">{event.lamport_timestamp}</td>
                <td>{new Date(event.wall_clock).toLocaleTimeString()}</td>
                <td className="mono">{event.run_id ? event.run_id.slice(0, 8) : "—"}</td>
                <td className="mono">{JSON.stringify(event.detail)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
