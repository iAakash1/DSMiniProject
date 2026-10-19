"use client";

import Link from "next/link";
import { ConnectionIndicator } from "@/components/ConnectionIndicator";
import { Header } from "@/components/Header";
import { ErrorState, LoadingState } from "@/components/StateViews";
import { StatusBadge } from "@/components/StatusBadge";
import { fetchJson, type CoordinatorRow, type ProtocolEventRow, type RunRow, type WorkerRow } from "@/lib/controlApi";
import { usePolling } from "@/lib/usePolling";
import { useEventStream } from "@/lib/useEventStream";

interface OverviewData {
  coordinators: CoordinatorRow[];
  workers: WorkerRow[];
  runs: RunRow[];
  events: ProtocolEventRow[];
}

const LEADERSHIP_EVENT_TYPES = new Set([
  "leader_suspected",
  "takeover_won",
  "takeover_lost",
  "leadership_change",
  "demoted_on_fencing_check",
]);

async function loadOverview(): Promise<OverviewData> {
  const [coordinators, workers, runs, events] = await Promise.all([
    fetchJson<{ coordinators: CoordinatorRow[] }>("/coordinators"),
    fetchJson<{ workers: WorkerRow[] }>("/workers"),
    fetchJson<{ runs: RunRow[] }>("/runs?limit=10"),
    fetchJson<{ events: ProtocolEventRow[] }>("/events?limit=400"),
  ]);
  return { coordinators: coordinators.coordinators, workers: workers.workers, runs: runs.runs, events: events.events };
}

export default function OverviewPage() {
  const { data, loading, error, connected, lastUpdatedAt } = usePolling(loadOverview, 4000);
  const { streaming, usingFallbackPolling } = useEventStream(1);

  const leader = data?.coordinators.find((coordinator) => coordinator.role === "leader");
  const standbys = data?.coordinators.filter((coordinator) => coordinator.role === "standby") ?? [];
  const healthyWorkers = data?.workers.filter((worker) => worker.status === "healthy").length ?? 0;
  const suspectedWorkers = data?.workers.filter((worker) => worker.status === "suspected").length ?? 0;
  const unavailableWorkers = data?.workers.filter((worker) => worker.status === "unavailable").length ?? 0;
  const currentWorkerInventory = healthyWorkers + suspectedWorkers;
  const activeRuns = data?.runs.filter((run) => ["created", "dispatched", "running"].includes(run.state)).length ?? 0;
  const leadershipEvents = (data?.events ?? []).filter((event) => LEADERSHIP_EVENT_TYPES.has(event.event_type)).slice(0, 8);

  return (
    <div>
      <Header
        title="System overview"
        subtitle={
          <>
            Live, backend-derived state of the distributed execution layer.{" "}
            <ConnectionIndicator connected={connected} lastUpdatedAt={lastUpdatedAt} />
          </>
        }
      />

      <div className="toolbar" style={{ marginBottom: "var(--d-4)" }}>
        <span className="connection-pill">
          <span className={`connection-dot ${streaming ? "live" : usingFallbackPolling ? "stale" : ""}`} />
          event stream: {streaming ? "connected (SSE)" : usingFallbackPolling ? "polling fallback" : "connecting…"}
        </span>
      </div>

      {error && <ErrorState message={error} />}
      {loading && !data && <LoadingState />}

      {data && (
        <>
          <div className="grid">
            <div className="card">
              <div className="stat-value">{data.coordinators.length}</div>
              <div className="stat-label">Coordinators registered</div>
            </div>
            <div className="card">
              <div className="stat-value">
                {leader ? <Link href={`/coordinators/${leader.id}`}>{leader.id}</Link> : "none elected"}
              </div>
              <div className="stat-label">Current leader · epoch {leader?.epoch ?? "—"}</div>
            </div>
            <div className="card">
              <div className="stat-value">{standbys.length}</div>
              <div className="stat-label">Standby coordinators</div>
            </div>
            <div className="card">
              <div className="stat-value">
                {healthyWorkers} / {currentWorkerInventory}
              </div>
              <div className="stat-label">
                Healthy workers ({suspectedWorkers} suspected)
                {unavailableWorkers > 0 && (
                  <>
                    {" · "}
                    <Link href="/workers">{unavailableWorkers} historical/unavailable</Link>
                  </>
                )}
              </div>
            </div>
            <div className="card">
              <div className="stat-value">{activeRuns}</div>
              <div className="stat-label">Active research runs</div>
            </div>
          </div>

          <div className="card">
            <div className="card-title">Recent leader transitions &amp; failure events</div>
            {leadershipEvents.length === 0 ? (
              <div className="empty-state">No leadership transitions observed in the last 50 events.</div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Process</th>
                    <th>Event</th>
                    <th>Wall clock</th>
                  </tr>
                </thead>
                <tbody>
                  {leadershipEvents.map((event) => (
                    <tr key={event.id}>
                      <td className="mono">{event.process_id}</td>
                      <td>
                        <StatusBadge value={event.event_type} />
                      </td>
                      <td>{new Date(event.wall_clock).toLocaleTimeString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="card">
            <div className="card-title">Recent research runs</div>
            {data.runs.length === 0 ? (
              <div className="empty-state">No runs dispatched yet.</div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>State</th>
                    <th>Generation</th>
                    <th>Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {data.runs.map((run) => (
                    <tr key={run.id}>
                      <td className="mono">{run.ticker}</td>
                      <td>
                        <StatusBadge value={run.state} />
                      </td>
                      <td>{run.generation}</td>
                      <td>{new Date(run.updated_at).toLocaleTimeString()}</td>
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
