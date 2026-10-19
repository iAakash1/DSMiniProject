"use client";

import { fetchJson } from "@/lib/controlApi";
import { usePolling } from "@/lib/usePolling";

interface HealthPayload {
  status: string;
  runtime: string;
}

export function Header({ title, subtitle }: { title: string; subtitle?: React.ReactNode }) {
  const { data, connected } = usePolling(() => fetchJson<HealthPayload>("/health"), 7000);

  return (
    <header className="topbar">
      <div>
        <div className="topbar-title">{title}</div>
        {subtitle && <div className="topbar-subtitle">{subtitle}</div>}
      </div>
      <div className="topbar-status">
        <span className={`connection-pill ${connected ? "" : "connection-pill-down"}`}>
          <span className={`connection-dot ${connected ? "live" : ""}`} />
          {connected ? `control API online · ${data?.runtime ?? "…"} runtime` : "control API unreachable"}
        </span>
      </div>
    </header>
  );
}
