"use client";

import { useState } from "react";
import { ConnectionIndicator } from "@/components/ConnectionIndicator";
import { Header } from "@/components/Header";
import { ErrorState, LoadingState, EmptyState } from "@/components/StateViews";
import { fetchJson, type ProtocolEventRow } from "@/lib/controlApi";
import { usePolling } from "@/lib/usePolling";

const RECOVERY_EVENT_TYPES = new Set([
  "leader_suspected",
  "takeover_won",
  "takeover_lost",
  "leadership_change",
  "demoted_on_fencing_check",
  "worker_health_changed",
]);

export default function EventsPage() {
  const [search, setSearch] = useState("");
  const [recoveryOnly, setRecoveryOnly] = useState(false);

  const { data, loading, error, connected, lastUpdatedAt } = usePolling(
    () => fetchJson<{ events: ProtocolEventRow[] }>("/events?limit=200").then((payload) => payload.events),
    5000,
  );

  const filtered = (data ?? []).filter((event) => {
    if (recoveryOnly && !RECOVERY_EVENT_TYPES.has(event.event_type)) return false;
    if (!search) return true;
    const haystack = `${event.process_id} ${event.event_type} ${JSON.stringify(event.detail)}`.toLowerCase();
    return haystack.includes(search.toLowerCase());
  });

  return (
    <div>
      <Header
        title="Event & recovery history"
        subtitle={
          <>
            A durable, searchable record of every coordinator, worker, leadership and run event — it survives a
            process restart because it is read from Postgres, not from memory.{" "}
            <ConnectionIndicator connected={connected} lastUpdatedAt={lastUpdatedAt} />
          </>
        }
      />

      <div className="toolbar">
        <input placeholder="Search events…" value={search} onChange={(event) => setSearch(event.target.value)} />
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "var(--t-small)", color: "var(--ink-muted)" }}>
          <input type="checkbox" checked={recoveryOnly} onChange={(event) => setRecoveryOnly(event.target.checked)} />
          Recovery events only
        </label>
      </div>

      {error && <ErrorState message={error} />}
      {loading && !data && <LoadingState />}
      {filtered.length === 0 && data && <EmptyState message="No events match this filter." />}

      {filtered.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Process</th>
              <th>Event</th>
              <th>Wall clock</th>
              <th>Lamport</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((event) => (
              <tr key={event.id}>
                <td className="mono">{event.process_id}</td>
                <td>{event.event_type}</td>
                <td>{new Date(event.wall_clock).toLocaleString()}</td>
                <td className="mono">{event.lamport_timestamp}</td>
                <td className="mono">{JSON.stringify(event.detail)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
