from __future__ import annotations

from distributed.common import config
from distributed.common.contracts import EvidenceRecord, WorkerGroup
from distributed.workers.common.adapters import providerResultToEvidence, testFixtureEvidence
from distributed.workers.common.workerapp import createWorkerApp


def quoteCapability(ticker: str) -> list[EvidenceRecord]:
    if config.useTestAdapters():
        return testFixtureEvidence("quote", ticker)
    from src import providers

    result = providers.market_data.get_price(ticker)
    return [providerResultToEvidence(result, "quote")]


def historyCapability(ticker: str) -> list[EvidenceRecord]:
    if config.useTestAdapters():
        return testFixtureEvidence("history", ticker)
    from src import providers

    result = providers.market_data.get_series(ticker, "3mo")
    return [providerResultToEvidence(result, "history")]


app = createWorkerApp(
    workerId=config.workerId(),
    group=WorkerGroup.market,
    capabilities={"quote": quoteCapability, "history": historyCapability},
)
