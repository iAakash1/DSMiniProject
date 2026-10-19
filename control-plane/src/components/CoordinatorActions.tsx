"use client";

import { useState } from "react";
import { postLifecycleAction, type CoordinatorRow, type LifecycleOutcome } from "@/lib/controlApi";

type Action = "stop" | "restart" | "delete";

const CONFIRM_COPY: Record<Action, (coordinator: CoordinatorRow) => string> = {
  stop: (coordinator) =>
    coordinator.role === "leader"
      ? `${coordinator.id} is the current leader. Stopping it is a deliberate fault-injection test: the Beacon protocol should detect the failure and a standby should take over at a higher epoch. Continue?`
      : `Stop ${coordinator.id}? It will leave the active mesh until restarted.`,
  restart: (coordinator) =>
    coordinator.role === "leader"
      ? `${coordinator.id} is the current leader. Restarting it briefly removes it from the mesh; it rejoins as a standby, not automatically as leader. Continue?`
      : `Restart ${coordinator.id}?`,
  delete: (coordinator) =>
    `Permanently delete ${coordinator.id}? This removes the container outright — there is no undo short of redeploying it by hand. ${
      coordinator.role === "leader" ? "It is the current leader: deleting it is a harder-edged version of a leader-stop test. " : ""
    }`,
};

export function CoordinatorActions({
  coordinator,
  onChanged,
  operatorTokenOverride,
  size = "normal",
}: {
  coordinator: CoordinatorRow;
  onChanged: () => void;
  operatorTokenOverride?: string;
  size?: "normal" | "compact";
}) {
  const [pendingAction, setPendingAction] = useState<Action | null>(null);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  async function run(action: Action) {
    const needsConfirm = action === "delete" || coordinator.role === "leader";
    if (needsConfirm && !window.confirm(CONFIRM_COPY[action](coordinator))) return;
    setPendingAction(action);
    setMessage(null);
    try {
      const outcome = (await postLifecycleAction(
        `/coordinators/${coordinator.id}/${action}`,
        {},
        operatorTokenOverride,
      )) as LifecycleOutcome;
      if (outcome.accepted) {
        setMessage({ tone: "success", text: `${action} on ${coordinator.id} succeeded: ${outcome.result}` });
      } else {
        const detailMessage = typeof outcome.detail?.message === "string" ? outcome.detail.message : outcome.result;
        setMessage({ tone: "error", text: `${action} on ${coordinator.id} was refused: ${detailMessage}` });
      }
      onChanged();
    } catch (caught) {
      setMessage({
        tone: "error",
        text: `${action} on ${coordinator.id} failed: ${caught instanceof Error ? caught.message : "unknown error"}`,
      });
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div>
      <div className={`toolbar action-toolbar-${size}`} style={{ marginBottom: 0 }}>
        <button disabled={pendingAction !== null} onClick={() => run("restart")}>
          {pendingAction === "restart" ? "Restarting…" : "Restart"}
        </button>
        <button disabled={pendingAction !== null} onClick={() => run("stop")}>
          {pendingAction === "stop" ? "Stopping…" : "Stop"}
        </button>
        <button className="danger" disabled={pendingAction !== null} onClick={() => run("delete")}>
          {pendingAction === "delete" ? "Deleting…" : "Delete"}
        </button>
      </div>
      {message && <div className={`action-message action-message-${message.tone}`}>{message.text}</div>}
    </div>
  );
}
