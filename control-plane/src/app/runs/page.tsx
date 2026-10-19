"use client";

import { Fragment, useState } from "react";
import { ConnectionIndicator } from "@/components/ConnectionIndicator";
import { Header } from "@/components/Header";
import { ErrorState, LoadingState, EmptyState } from "@/components/StateViews";
import { StatusBadge } from "@/components/StatusBadge";
import { controlApiBaseUrl, fetchJson, postJson, type ProtocolEventRow, type RunRow } from "@/lib/controlApi";
import { usePolling } from "@/lib/usePolling";

interface CapabilityOutcome {
  status: string;
  error: string | null;
  workerId?: string;
  workerGroup?: string;
  latencyMs?: number | null;
  evidence?: unknown[];
}

interface RunDetail {
  run: RunRow;
  attempts: unknown[];
  events: ProtocolEventRow[];
}

function capabilitiesOf(run: RunRow): Record<string, CapabilityOutcome> {
  const result = run.result as { capabilities?: Record<string, CapabilityOutcome> } | null;
  return result?.capabilities ?? {};
}

function durationMs(fromIso: string, toIso: string): number {
  return new Date(toIso).getTime() - new Date(fromIso).getTime();
}

export default function RunsPage() {
  const { data, loading, error, connected, lastUpdatedAt, reload } = usePolling(
    () => fetchJson<{ runs: RunRow[] }>("/runs?limit=50").then((payload) => payload.runs),
    3000,
  );
  const [ticker, setTicker] = useState("AAPL");
  const [dispatching, setDispatching] = useState(false);
  const [dispatchMessage, setDispatchMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, RunDetail | "loading" | "error">>({});

  async function dispatchRun() {
    setDispatching(true);
    setDispatchMessage(null);
    try {
      const payload = (await postJson("/runs", {
        ticker,
        capabilities: ["quote", "history", "fundamentals", "company", "news", "macro"],
      })) as { runId: string; state: string };
      setDispatchMessage({ tone: "success", text: `dispatched as run ${payload.runId} → ${payload.state}` });
      reload();
    } catch (caught) {
      setDispatchMessage({ tone: "error", text: caught instanceof Error ? caught.message : "dispatch failed" });
    } finally {
      setDispatching(false);
    }
  }

  async function toggleExpand(runId: string) {
    if (expandedRunId === runId) {
      setExpandedRunId(null);
      return;
    }
    setExpandedRunId(runId);
    if (details[runId]) return;
    setDetails((prev) => ({ ...prev, [runId]: "loading" }));
    try {
      const detail = await fetchJson<RunDetail>(`/runs/${runId}`);
      setDetails((prev) => ({ ...prev, [runId]: detail }));
    } catch {
      setDetails((prev) => ({ ...prev, [runId]: "error" }));
    }
  }

  return (
    <div>
      <Header
        title="Research runs"
        subtitle={
          <>
            Dispatch and lifecycle of each distributed research run, aggregated across all three worker groups.{" "}
            <ConnectionIndicator connected={connected} lastUpdatedAt={lastUpdatedAt} />
          </>
        }
      />

      <div className="toolbar">
        <input value={ticker} onChange={(event) => setTicker(event.target.value.toUpperCase())} placeholder="Ticker" />
        <button className="primary" disabled={dispatching} onClick={dispatchRun}>
          {dispatching ? "Dispatching…" : "Dispatch run"}
        </button>
        <span className="mono" style={{ fontSize: "var(--t-small)", color: "var(--ink-faint)" }}>
          proxied to the leader through {controlApiBaseUrl()}
        </span>
      </div>
      {dispatchMessage && <div className={`action-message action-message-${dispatchMessage.tone}`}>{dispatchMessage.text}</div>}

      {error && <ErrorState message={error} />}
      {loading && !data && <LoadingState />}
      {data && data.length === 0 && <EmptyState message="No research runs yet — dispatch one above." />}

      {data && data.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>State</th>
              <th>Epoch</th>
              <th>Generation</th>
              <th>Created</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {data.map((run) => {
              const capabilities = capabilitiesOf(run);
              const capabilityEntries = Object.entries(capabilities);
              const isExpanded = expandedRunId === run.id;
              const detail = details[run.id];
              return (
                <Fragment key={run.id}>
                  <tr className="row-expandable" onClick={() => toggleExpand(run.id)}>
                    <td className="mono">{run.ticker}</td>
                    <td>
                      <StatusBadge value={run.state} />
                    </td>
                    <td className="mono">{run.leader_epoch}</td>
                    <td className="mono">{run.generation}</td>
                    <td>{new Date(run.created_at).toLocaleTimeString()}</td>
                    <td>{new Date(run.updated_at).toLocaleTimeString()}</td>
                  </tr>
                  {isExpanded && (
                    <tr className="row-detail">
                      <td colSpan={6}>
                        {capabilityEntries.length === 0 ? (
                          <div className="empty-state">
                            {run.state === "created" || run.state === "dispatched" || run.state === "running"
                              ? "Still in flight — no capability outcomes recorded yet."
                              : "No capability outcomes recorded for this run."}
                          </div>
                        ) : (
                          <table>
                            <thead>
                              <tr>
                                <th>Capability</th>
                                <th>Status</th>
                                <th>Worker group</th>
                                <th>Worker</th>
                                <th>Latency</th>
                                <th>Evidence</th>
                                <th>Error</th>
                              </tr>
                            </thead>
                            <tbody>
                              {capabilityEntries.map(([capability, outcome]) => (
                                <tr key={capability}>
                                  <td className="mono">{capability}</td>
                                  <td>
                                    <StatusBadge value={outcome.status} />
                                  </td>
                                  <td>{outcome.workerGroup ?? "—"}</td>
                                  <td className="mono">{outcome.workerId ?? "—"}</td>
                                  <td className="mono">{outcome.latencyMs != null ? `${outcome.latencyMs.toFixed(1)}ms` : "—"}</td>
                                  <td className="mono">{outcome.evidence?.length ?? 0}</td>
                                  <td>{outcome.error ?? "—"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}

                        <div className="card-title" style={{ marginTop: "var(--d-3)" }}>
                          Event timeline
                        </div>
                        {detail === "loading" && <div className="empty-state">Loading…</div>}
                        {detail === "error" && <div className="empty-state">Could not load the event timeline.</div>}
                        {detail && detail !== "loading" && detail !== "error" && (
                          detail.events.length === 0 ? (
                            <div className="empty-state">No protocol events recorded for this run.</div>
                          ) : (
                            <>
                              <table>
                                <thead>
                                  <tr>
                                    <th>Wall clock</th>
                                    <th>+ms since previous</th>
                                    <th>Process</th>
                                    <th>Event</th>
                                    <th>Lamport</th>
                                    <th>Detail</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {detail.events.map((event, index) => (
                                    <tr key={event.id}>
                                      <td className="mono">{new Date(event.wall_clock).toLocaleTimeString(undefined, { hour12: false, minute: "2-digit", second: "2-digit", fractionalSecondDigits: 3 } as Intl.DateTimeFormatOptions)}</td>
                                      <td className="mono">{index === 0 ? "—" : `+${durationMs(detail.events[index - 1].wall_clock, event.wall_clock)}`}</td>
                                      <td className="mono">{event.process_id}</td>
                                      <td>{event.event_type}</td>
                                      <td className="mono">{event.lamport_timestamp}</td>
                                      <td className="mono">{JSON.stringify(event.detail)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                              <div className="stat-label" style={{ marginTop: "var(--d-2)" }}>
                                Total: {durationMs(detail.events[0].wall_clock, detail.events[detail.events.length - 1].wall_clock)}ms across {detail.events.length} recorded events
                              </div>
                            </>
                          )
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
