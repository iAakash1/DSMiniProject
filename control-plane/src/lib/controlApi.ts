export function controlApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_CONTROL_API_URL ?? "http://localhost:7900";
}

export class ControlApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function fetchJson<ResponseType>(path: string): Promise<ResponseType> {
  const response = await fetch(`${controlApiBaseUrl()}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new ControlApiError(`${path} returned ${response.status}`, response.status);
  }
  return (await response.json()) as ResponseType;
}

export async function postJson(path: string, body: unknown): Promise<unknown> {
  const response = await fetch(`${controlApiBaseUrl()}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new ControlApiError(payload?.detail ?? `${path} returned ${response.status}`, response.status);
  }
  return payload;
}

export async function postAction(path: string, operatorToken: string, body: unknown = {}): Promise<unknown> {
  const response = await fetch(`${controlApiBaseUrl()}${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${operatorToken}`,
    },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new ControlApiError(payload?.detail ?? `${path} returned ${response.status}`, response.status);
  }
  return payload;
}

export interface LifecycleOutcome {
  accepted: boolean;
  result: string;
  detail?: Record<string, unknown>;
}

export async function postLifecycleAction(
  path: string,
  body: unknown = {},
  overrideOperatorToken?: string,
): Promise<LifecycleOutcome> {
  if (overrideOperatorToken) {
    return (await postAction(path, overrideOperatorToken, body)) as LifecycleOutcome;
  }
  const response = await fetch(`/api/control${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new ControlApiError(payload?.detail ?? `${path} returned ${response.status}`, response.status);
  }
  return payload as LifecycleOutcome;
}

export interface CoordinatorRow {
  id: string;
  host: string;
  port: number;
  role: string;
  epoch: number;
  lamport_timestamp: number;
  last_beacon_sent_at: string | null;
  last_beacon_from_leader_at: string | null;
  registered_at: string;
  runtime_kind: string;
  runtime_ref: string | null;
}

export interface WorkerRow {
  id: string;
  worker_group: string;
  host: string;
  port: number;
  status: string;
  last_heartbeat_at: string | null;
  last_sequence: number;
  active_attempts: number;
  registered_at: string;
}

export interface ProtocolEventRow {
  id: number;
  process_id: string;
  process_role: string;
  event_type: string;
  lamport_timestamp: number;
  wall_clock: string;
  run_id: string | null;
  request_id: string | null;
  detail: Record<string, unknown>;
}

export interface RunRow {
  id: string;
  ticker: string;
  state: string;
  created_at: string;
  updated_at: string;
  leader_epoch: number;
  generation: number;
  result: Record<string, unknown> | null;
}
