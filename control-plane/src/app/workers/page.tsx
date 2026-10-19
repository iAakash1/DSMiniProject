"use client";

import { ConnectionIndicator } from "@/components/ConnectionIndicator";
import { Header } from "@/components/Header";
import { ErrorState, LoadingState, EmptyState } from "@/components/StateViews";
import { StatusBadge } from "@/components/StatusBadge";
import { fetchJson, type WorkerRow } from "@/lib/controlApi";
import { usePolling } from "@/lib/usePolling";

function secondsSince(timestamp: string | null): string {
  if (!timestamp) return "never";
  const elapsed = (Date.now() - new Date(timestamp).getTime()) / 1000;
  return `${elapsed.toFixed(1)}s ago`;
}

export default function WorkersPage() {
  const { data, loading, error, connected, lastUpdatedAt } = usePolling(
    () => fetchJson<{ workers: WorkerRow[] }>("/workers").then((payload) => payload.workers),
    3000,
  );

  return (
    <div>
      <Header
        title="Worker health"
        subtitle={
          <>
            Health is computed by the coordinator receiving heartbeats, not inferred by this page.{" "}
            <ConnectionIndicator connected={connected} lastUpdatedAt={lastUpdatedAt} />
          </>
        }
      />

      {error && <ErrorState message={error} />}
      {loading && !data && <LoadingState />}
      {data && data.length === 0 && <EmptyState message="No workers have registered a heartbeat yet." />}

      {data && data.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Worker</th>
              <th>Group</th>
              <th>Status</th>
              <th>Last heartbeat</th>
              <th>Sequence</th>
              <th>Active attempts</th>
            </tr>
          </thead>
          <tbody>
            {data.map((worker) => (
              <tr key={worker.id}>
                <td className="mono">{worker.id}</td>
                <td>{worker.worker_group}</td>
                <td>
                  <StatusBadge value={worker.status} />
                </td>
                <td>{secondsSince(worker.last_heartbeat_at)}</td>
                <td className="mono">{worker.last_sequence}</td>
                <td className="mono">{worker.active_attempts}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
