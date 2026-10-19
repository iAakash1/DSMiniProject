from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from distributed.common.contracts import EvidenceRecord


def providerResultToEvidence(result: Any, capability: str) -> EvidenceRecord:
    if result.ok:
        return EvidenceRecord(
            vendor=result.source or "unknown",
            capability=capability,
            status="ok",
            observedAt=result.fetched_at,
            data=result.data.model_dump() if hasattr(result.data, "model_dump") else {"value": result.data},
        )
    return EvidenceRecord(
        vendor=result.source or "none",
        capability=capability,
        status="unavailable" if result.outage else "no_data",
        observedAt=result.fetched_at,
        error=result.error,
    )


def testFixtureEvidence(capability: str, ticker: str) -> list[EvidenceRecord]:
    fixtures = {
        "quote": {"price": 123.45, "currency": "USD", "symbol": ticker},
        "history": {"bars": 252, "symbol": ticker},
        "fundamentals": {"revenue": 1_000_000_000, "symbol": ticker},
        "company": {"name": f"{ticker} Test Co", "symbol": ticker},
        "news": {"headlines": 5, "symbol": ticker},
        "macro": {"regime": "stable"},
    }
    return [
        EvidenceRecord(
            vendor="test-fixture",
            capability=capability,
            status="ok",
            observedAt=datetime.now(timezone.utc),
            data=fixtures.get(capability, {"ticker": ticker}),
        )
    ]
