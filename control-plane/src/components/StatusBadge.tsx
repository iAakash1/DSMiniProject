const toneByValue: Record<string, string> = {
  leader: "badge-pos",
  healthy: "badge-pos",
  completed: "badge-pos",
  success: "badge-pos",
  standby: "badge-null",
  pending: "badge-null",
  created: "badge-null",
  suspected: "badge-warn",
  partially_completed: "badge-warn",
  partial: "badge-warn",
  recovering: "badge-warn",
  dispatched: "badge-warn",
  running: "badge-warn",
  unavailable: "badge-neg",
  failed: "badge-neg",
  timeout: "badge-neg",
  unknown: "badge-null",
  takeover_won: "badge-pos",
  leadership_change: "badge-pos",
  leader_suspected: "badge-warn",
  demoted_on_fencing_check: "badge-warn",
  worker_health_changed: "badge-warn",
  takeover_lost: "badge-neg",
};

export function StatusBadge({ value }: { value: string }) {
  const tone = toneByValue[value] ?? "badge-null";
  return <span className={`badge ${tone}`}>{value}</span>;
}
