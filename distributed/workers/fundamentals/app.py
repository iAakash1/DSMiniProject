from __future__ import annotations

from distributed.common import config
from distributed.common.contracts import EvidenceRecord, WorkerGroup
from distributed.workers.common.adapters import providerResultToEvidence, testFixtureEvidence
from distributed.workers.common.workerapp import createWorkerApp


def fundamentalsCapability(ticker: str) -> list[EvidenceRecord]:
    if config.useTestAdapters():
        return testFixtureEvidence("fundamentals", ticker)
    from src import providers

    result = providers.fundamentals.get_fundamentals(ticker)
    return [providerResultToEvidence(result, "fundamentals")]


def companyCapability(ticker: str) -> list[EvidenceRecord]:
    if config.useTestAdapters():
        return testFixtureEvidence("company", ticker)
    from src import providers

    result = providers.fundamentals.get_company(ticker)
    return [providerResultToEvidence(result, "company")]


app = createWorkerApp(
    workerId=config.workerId(),
    group=WorkerGroup.fundamentals,
    capabilities={"fundamentals": fundamentalsCapability, "company": companyCapability},
)
