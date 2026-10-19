"use client";

import Link from "next/link";
import { useState } from "react";
import { CoordinatorActions } from "@/components/CoordinatorActions";
import { ConnectionIndicator } from "@/components/ConnectionIndicator";
import { Header } from "@/components/Header";
import { ErrorState, LoadingState, EmptyState } from "@/components/StateViews";
import { StatusBadge } from "@/components/StatusBadge";
import { fetchJson, postLifecycleAction, type CoordinatorRow, type LifecycleOutcome } from "@/lib/controlApi";
import { usePolling } from "@/lib/usePolling";

async function loadCoordinators(): Promise<CoordinatorRow[]> {
  const payload = await fetchJson<{ coordinators: CoordinatorRow[] }>("/coordinators");
  return payload.coordinators;
}

export default function CoordinatorsPage() {
  const { data, loading, error, connected, lastUpdatedAt, reload } = usePolling(loadCoordinators, 3000);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [operatorTokenOverride, setOperatorTokenOverride] = useState("");
  const [addPending, setAddPending] = useState(false);
  const [addMessage, setAddMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  async function addCoordinator() {
    setAddPending(true);
    setAddMessage(null);
    try {
      const outcome = (await postLifecycleAction(
        "/coordinators",
        { role: "coordinator" },
        operatorTokenOverride || undefined,
      )) as LifecycleOutcome;
      if (outcome.accepted) {
        setAddMessage({ tone: "success", text: `add coordinator succeeded: ${outcome.result}` });
      } else {
        const detailMessage = typeof outcome.detail?.message === "string" ? outcome.detail.message : outcome.result;
        setAddMessage({ tone: "error", text: `add coordinator was refused: ${detailMessage}` });
      }
      reload();
    } catch (caught) {
      setAddMessage({ tone: "error", text: caught instanceof Error ? caught.message : "add coordinator failed" });
    } finally {
      setAddPending(false);
    }
  }

  return (
    <div>
      <Header
        title="Coordinator inventory"
        subtitle={
          <>
            Every row is a real coordinator instance discovered by the control API, not a hardcoded card.{" "}
            <ConnectionIndicator connected={connected} lastUpdatedAt={lastUpdatedAt} />
          </>
        }
      />

      <div className="toolbar">
        <button className="primary" disabled={addPending} onClick={addCoordinator}>
          {addPending ? "Adding…" : "Add coordinator"}
        </button>
        <button className="ghost" onClick={() => setShowAdvanced((value) => !value)}>
          {showAdvanced ? "Hide advanced" : "Advanced: use a different operator token"}
        </button>
        {showAdvanced && (
          <input
            type="password"
            placeholder="operator token override"
            value={operatorTokenOverride}
            onChange={(event) => setOperatorTokenOverride(event.target.value)}
          />
        )}
      </div>

      {addMessage && <div className={`action-message action-message-${addMessage.tone}`}>{addMessage.text}</div>}
      {error && <ErrorState message={error} />}
      {loading && !data && <LoadingState />}
      {data && data.length === 0 && <EmptyState message="No coordinators registered yet." />}

      {data && data.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Identity</th>
              <th>Role</th>
              <th>Epoch</th>
              <th>Lamport</th>
              <th>Last beacon from leader</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.map((coordinator) => (
              <tr key={coordinator.id}>
                <td>
                  <Link href={`/coordinators/${coordinator.id}`} className="mono">
                    {coordinator.id}
                  </Link>
                </td>
                <td>
                  <StatusBadge value={coordinator.role} />
                </td>
                <td className="mono">{coordinator.epoch}</td>
                <td className="mono">{coordinator.lamport_timestamp}</td>
                <td>{coordinator.last_beacon_from_leader_at ? new Date(coordinator.last_beacon_from_leader_at).toLocaleTimeString() : "never"}</td>
                <td>
                  <CoordinatorActions
                    coordinator={coordinator}
                    onChanged={reload}
                    operatorTokenOverride={operatorTokenOverride || undefined}
                    size="compact"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
