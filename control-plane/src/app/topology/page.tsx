"use client";

import { ConnectionIndicator } from "@/components/ConnectionIndicator";
import { Header } from "@/components/Header";
import { ErrorState, LoadingState } from "@/components/StateViews";
import { fetchJson } from "@/lib/controlApi";
import { usePolling } from "@/lib/usePolling";

interface TopologyNode {
  id: string;
  kind: "coordinator" | "worker" | "control-api";
  role?: string;
  epoch?: number;
  group?: string;
  status?: string;
}

interface TopologyEdge {
  source: string;
  target: string;
  kind: string;
}

interface TopologyData {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

function colorForNode(node: TopologyNode): string {
  if (node.kind === "control-api") return "var(--ink-muted)";
  if (node.kind === "coordinator") {
    return node.role === "leader" ? "var(--e-pos)" : "var(--accent)";
  }
  if (node.status === "healthy") return "var(--e-pos)";
  if (node.status === "suspected") return "var(--e-warn)";
  return "var(--e-null)";
}

const LEGEND = [
  { swatch: "var(--e-pos)", label: "Coordinator — leader" },
  { swatch: "var(--accent)", label: "Coordinator — standby" },
  { swatch: "var(--e-pos)", label: "Worker — healthy", shape: "square" as const },
  { swatch: "var(--e-warn)", label: "Worker — suspected", shape: "square" as const },
  { swatch: "var(--e-null)", label: "Worker — unavailable", shape: "square" as const },
  { swatch: "var(--ink-muted)", label: "Control API", shape: "square" as const },
];

export default function TopologyPage() {
  const { data, loading, error, connected, lastUpdatedAt } = usePolling(() => fetchJson<TopologyData>("/topology"), 4000);

  const controlApiNode = data?.nodes.find((node) => node.kind === "control-api");
  const coordinators = data?.nodes.filter((node) => node.kind === "coordinator") ?? [];
  const workers = data?.nodes.filter((node) => node.kind === "worker") ?? [];

  const width = 960;
  const controlApiY = 36;
  const coordinatorY = 140;
  const workerY = 300;
  const positions = new Map<string, { x: number; y: number }>();
  if (controlApiNode) positions.set(controlApiNode.id, { x: width / 2, y: controlApiY });
  coordinators.forEach((node, index) => positions.set(node.id, { x: ((index + 1) * width) / (coordinators.length + 1), y: coordinatorY }));
  workers.forEach((node, index) => positions.set(node.id, { x: ((index + 1) * width) / (workers.length + 1), y: workerY }));

  function strokeFor(edge: TopologyEdge): string {
    if (edge.kind === "beacon_mesh") return "var(--accent-line)";
    if (edge.kind === "control_link") return "var(--rule-strong)";
    return "var(--rule-strong)";
  }

  return (
    <div>
      <Header
        title="Network topology"
        subtitle={
          <>
            Nodes are discovered instances; edges are drawn only from configuration (the coordinator beacon mesh, the
            control API&apos;s known coordinators) or observed communication (the coordinator that last received a
            worker&apos;s heartbeat).{" "}
            <ConnectionIndicator connected={connected} lastUpdatedAt={lastUpdatedAt} />
          </>
        }
      />

      {error && <ErrorState message={error} />}
      {loading && !data && <LoadingState />}

      {data && (
        <div className="card">
          <svg viewBox={`0 0 ${width} 360`} width="100%" style={{ maxWidth: width, height: "auto" }} role="img" aria-label="service topology">
            {data.edges.map((edge, index) => {
              const from = positions.get(edge.source);
              const to = positions.get(edge.target);
              if (!from || !to) return null;
              return (
                <line
                  key={index}
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke={strokeFor(edge)}
                  strokeWidth={edge.kind === "heartbeat" ? 1 : 1.5}
                  strokeDasharray={edge.kind === "control_link" ? "3 3" : undefined}
                />
              );
            })}
            {controlApiNode && (
              <g>
                <rect
                  x={positions.get(controlApiNode.id)!.x - 40}
                  y={positions.get(controlApiNode.id)!.y - 14}
                  width={80}
                  height={28}
                  rx={6}
                  fill="var(--p-raised)"
                  stroke={colorForNode(controlApiNode)}
                  strokeWidth={1.5}
                  style={{ filter: "drop-shadow(0 1px 3px rgba(15, 20, 30, 0.12))" }}
                />
                <text
                  x={positions.get(controlApiNode.id)!.x}
                  y={positions.get(controlApiNode.id)!.y + 4}
                  textAnchor="middle"
                  fontSize={11}
                  fill="var(--ink)"
                >
                  control-api
                </text>
              </g>
            )}
            {coordinators.map((node) => {
              const position = positions.get(node.id)!;
              return (
                <g key={node.id}>
                  <circle
                    cx={position.x}
                    cy={position.y}
                    r={22}
                    fill={colorForNode(node)}
                    stroke="var(--p-panel)"
                    strokeWidth={3}
                    style={{ filter: "drop-shadow(0 2px 4px rgba(15, 20, 30, 0.18))" }}
                  />
                  <text x={position.x} y={position.y + 38} textAnchor="middle" fontSize={11} fill="var(--ink-muted)">
                    {node.id}
                  </text>
                  <text x={position.x} y={position.y + 52} textAnchor="middle" fontSize={10} fill="var(--ink-faint)">
                    {node.role} · epoch {node.epoch}
                  </text>
                </g>
              );
            })}
            {workers.map((node) => {
              const position = positions.get(node.id)!;
              return (
                <g key={node.id}>
                  <rect
                    x={position.x - 16}
                    y={position.y - 16}
                    width={32}
                    height={32}
                    rx={6}
                    fill={colorForNode(node)}
                    stroke="var(--p-panel)"
                    strokeWidth={2.5}
                    style={{ filter: "drop-shadow(0 2px 4px rgba(15, 20, 30, 0.18))" }}
                  />
                  <text x={position.x} y={position.y + 32} textAnchor="middle" fontSize={10} fill="var(--ink-muted)">
                    {node.group}
                  </text>
                </g>
              );
            })}
          </svg>
          <div className="topology-legend">
            {LEGEND.map((item) => (
              <span key={item.label} className="legend-item">
                <span className={`legend-swatch${item.shape === "square" ? " legend-swatch-square" : ""}`} style={{ background: item.swatch }} />
                {item.label}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
