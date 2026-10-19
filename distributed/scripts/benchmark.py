from __future__ import annotations

import argparse
import asyncio
import csv
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx


@dataclass
class RequestOutcome:
    latencyMs: float
    state: str
    errored: bool


@dataclass
class BenchmarkResult:
    replicaCount: int
    concurrency: int
    totalRequests: int
    outcomes: list[RequestOutcome] = field(default_factory=list)
    wallClockSeconds: float = 0.0

    def completed(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.state == "completed")

    def partial(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.state == "partially_completed")

    def errored(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.errored)

    def latenciesMs(self) -> list[float]:
        return [outcome.latencyMs for outcome in self.outcomes if not outcome.errored]

    def throughputPerSecond(self) -> float:
        return self.totalRequests / self.wallClockSeconds if self.wallClockSeconds > 0 else 0.0

    def percentile(self, fraction: float) -> float:
        latencies = sorted(self.latenciesMs())
        if not latencies:
            return 0.0
        index = min(len(latencies) - 1, int(len(latencies) * fraction))
        return latencies[index]

    def summary(self) -> dict:
        return {
            "replicaCount": self.replicaCount,
            "concurrency": self.concurrency,
            "totalRequests": self.totalRequests,
            "completed": self.completed(),
            "partiallyCompleted": self.partial(),
            "errored": self.errored(),
            "errorRate": self.errored() / self.totalRequests if self.totalRequests else 0.0,
            "partialRate": self.partial() / self.totalRequests if self.totalRequests else 0.0,
            "throughputPerSecond": round(self.throughputPerSecond(), 3),
            "latencyP50Ms": round(self.percentile(0.5), 2),
            "latencyP95Ms": round(self.percentile(0.95), 2),
            "wallClockSeconds": round(self.wallClockSeconds, 2),
        }


async def countHealthyWorkers(controlApiUrl: str, group: str) -> int:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{controlApiUrl}/workers", timeout=5.0)
        response.raise_for_status()
        workers = response.json()["workers"]
    return sum(1 for worker in workers if worker["worker_group"] == group and worker["status"] == "healthy")


async def runOneRequest(client: httpx.AsyncClient, controlApiUrl: str, ticker: str, capabilities: list[str]) -> RequestOutcome:
    started = time.monotonic()
    try:
        response = await client.post(f"{controlApiUrl}/runs", json={"ticker": ticker, "capabilities": capabilities}, timeout=20.0)
        latencyMs = (time.monotonic() - started) * 1000.0
        if response.status_code != 200:
            return RequestOutcome(latencyMs=latencyMs, state="http_error", errored=True)
        payload = response.json()
        return RequestOutcome(latencyMs=latencyMs, state=payload["state"], errored=False)
    except httpx.HTTPError:
        latencyMs = (time.monotonic() - started) * 1000.0
        return RequestOutcome(latencyMs=latencyMs, state="transport_error", errored=True)


async def runBenchmark(
    controlApiUrl: str,
    group: str,
    capabilities: list[str],
    totalRequests: int,
    concurrency: int,
    tickers: list[str],
) -> BenchmarkResult:
    replicaCount = await countHealthyWorkers(controlApiUrl, group)
    semaphore = asyncio.Semaphore(concurrency)
    outcomes: list[RequestOutcome] = []

    async def bounded(index: int, client: httpx.AsyncClient) -> None:
        async with semaphore:
            ticker = tickers[index % len(tickers)]
            outcomes.append(await runOneRequest(client, controlApiUrl, ticker, capabilities))

    startedAt = time.monotonic()
    async with httpx.AsyncClient() as client:
        await asyncio.gather(*(bounded(index, client) for index in range(totalRequests)))
    wallClockSeconds = time.monotonic() - startedAt

    return BenchmarkResult(replicaCount=replicaCount, concurrency=concurrency, totalRequests=totalRequests, outcomes=outcomes, wallClockSeconds=wallClockSeconds)


def writeCsvRow(path: Path, summary: dict) -> None:
    fileExists = path.exists()
    with path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary.keys()))
        if not fileExists:
            writer.writeheader()
        writer.writerow(summary)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Scalability benchmark against the distributed research-dispatch path")
    parser.add_argument("--control-api-url", default="http://localhost:7900")
    parser.add_argument("--group", default="market")
    parser.add_argument("--capabilities", default="quote")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--tickers", default="AAPL,MSFT,NVDA,GOOGL,AMZN")
    parser.add_argument("--output-csv", default="distributed/scripts/benchmark-results.csv")
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    result = await runBenchmark(
        controlApiUrl=args.control_api_url,
        group=args.group,
        capabilities=args.capabilities.split(","),
        totalRequests=args.requests,
        concurrency=args.concurrency,
        tickers=args.tickers.split(","),
    )
    summary = result.summary()
    print(json.dumps(summary, indent=2))
    writeCsvRow(Path(args.output_csv), summary)
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
