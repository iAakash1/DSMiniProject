"use client";

import { useParams } from "next/navigation";
import { CoordinatorActions } from "@/components/CoordinatorActions";
import { ConnectionIndicator } from "@/components/ConnectionIndicator";
import { Header } from "@/components/Header";
import { ErrorState, LoadingState } from "@/components/StateViews";
import { StatusBadge } from "@/components/StatusBadge";
import { fetchJson, type CoordinatorRow, type ProtocolEventRow } from "@/lib/controlApi";
import { usePolling } from "@/lib/usePolling";

interface CoordinatorDetail {
  coordinator: CoordinatorRow;
  recentEvents: ProtocolEventRow[];
}

export default function CoordinatorDetailPage() {
  const params = useParams<{ id: string }>();
  const coordinatorId = params.id;

  const { data, loading, error, connected, lastUpdatedAt, reload } = usePolling(
    () => fetchJson<CoordinatorDetail>(`/coordinators/${coordinatorId}`),
    3000,
  );

  return (
    <div>
      <Header
        title={coordinatorId}
        subtitle={
          <>
            Generated from one reusable template, filled with this instance&apos;s live state.{" "}
            <ConnectionIndicator connected={connected} lastUpdatedAt={lastUpdatedAt} />
          </>
        }
      />

      {error && <ErrorState message={error} />}
      {loading && !data && <LoadingState />}

      {data && (
        <>
          <div className="grid">
            <div className="card">
              <div className="stat-value">
                <StatusBadge value={data.coordinator.role} />
              </div>
              <div className="stat-label">Role</div>
            </div>
            <div className="card">
              <div className="stat-value">{data.coordinator.epoch}</div>
              <div className="stat-label">Leadership epoch</div>
            </div>
            <div className="card">
              <div className="stat-value">{data.coordinator.lamport_timestamp}</div>
              <div className="stat-label">Lamport clock</div>
            </div>
            <div className="card">
              <div className="stat-value">{data.coordinator.runtime_kind}</div>
              <div className="stat-label">Runtime ({data.coordinator.host}:{data.coordinator.port})</div>
            </div>
          </div>

          <div className="card">
            <div className="card-title">Lifecycle operations</div>
            <CoordinatorActions coordinator={data.coordinator} onChanged={reload} />
          </div>

          <div className="card">
            <div className="card-title">Recent protocol activity</div>
            {data.recentEvents.length === 0 ? (
              <div className="empty-state">No protocol events recorded for this instance yet.</div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>Lamport</th>
                    <th>Wall clock</th>
                    <th>Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recentEvents.map((event) => (
                    <tr key={event.id}>
                      <td>{event.event_type}</td>
                      <td className="mono">{event.lamport_timestamp}</td>
                      <td>{new Date(event.wall_clock).toLocaleTimeString()}</td>
                      <td className="mono">{JSON.stringify(event.detail)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
