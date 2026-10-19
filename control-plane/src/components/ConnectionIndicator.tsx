"use client";

import { useEffect, useState } from "react";

export function ConnectionIndicator({
  connected,
  lastUpdatedAt,
}: {
  connected: boolean;
  lastUpdatedAt: Date | null;
}) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const staleAfterMs = 15000;
  const isStale = lastUpdatedAt !== null && now - lastUpdatedAt.getTime() > staleAfterMs;
  const dotClass = !connected ? "" : isStale ? "stale" : "live";
  const label = !connected
    ? "disconnected from control API"
    : isStale
      ? `stale — last update ${lastUpdatedAt?.toLocaleTimeString()}`
      : `live — updated ${lastUpdatedAt?.toLocaleTimeString() ?? ""}`;
  return (
    <span className="connection-pill">
      <span className={`connection-dot ${dotClass}`} />
      {label}
    </span>
  );
}
