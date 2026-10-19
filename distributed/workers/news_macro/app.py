from __future__ import annotations

from distributed.common import config
from distributed.common.contracts import EvidenceRecord, WorkerGroup
from distributed.workers.common.adapters import providerResultToEvidence, testFixtureEvidence
from distributed.workers.common.workerapp import createWorkerApp


def newsCapability(ticker: str) -> list[EvidenceRecord]:
    if config.useTestAdapters():
        return testFixtureEvidence("news", ticker)
    from src import providers

    evidenceItems = providers.news.news_evidence(ticker)
    return [
        EvidenceRecord(
            vendor=item.provider,
            capability="news",
            status=item.status,
            observedAt=item.fetched_at,
            data={"headline_count": len(item.data)} if item.ok and isinstance(item.data, list) else None,
            error=item.error,
        )
        for item in evidenceItems
    ]


def macroCapability(ticker: str) -> list[EvidenceRecord]:
    if config.useTestAdapters():
        return testFixtureEvidence("macro", ticker)
    from src import providers

    result = providers.macro.get_macro()
    return [providerResultToEvidence(result, "macro")]


app = createWorkerApp(
    workerId=config.workerId(),
    group=WorkerGroup.news_macro,
    capabilities={"news": newsCapability, "macro": macroCapability},
)
