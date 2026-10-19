from __future__ import annotations

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable
from uuid import UUID

import grpc
import httpx
from fastapi import FastAPI, HTTPException

from distributed.common import config
from distributed.common.contracts import (
    AttemptStatus,
    CapabilityRequest,
    EvidenceRecord,
    HeartbeatMessage,
    WorkerGroup,
    WorkerResponse,
)
from distributed.common.lamportclock import LamportClock
from distributed.proto.v1 import worker_pb2, worker_pb2_grpc

logger = logging.getLogger("distributed.worker")

CapabilityHandler = Callable[[str], list[EvidenceRecord]]


class WorkerRuntime:
    def __init__(self, workerId: str, group: WorkerGroup, host: str, port: int, coordinatorBaseUrls: list[str]) -> None:
        self.workerId = workerId
        self.group = group
        self.host = host
        self.port = port
        self.coordinatorBaseUrls = coordinatorBaseUrls
        self.clock = LamportClock(workerId)
        self.sequence = 0
        self.activeAttempts = 0
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def heartbeatOnce(self, client: httpx.AsyncClient) -> bool:
        self.sequence += 1
        message = HeartbeatMessage(
            workerId=self.workerId,
            workerGroup=self.group,
            sequence=self.sequence,
            host=self.host,
            port=self.port,
            lamportTimestamp=self.clock.tick(),
            sentAt=datetime.now(timezone.utc),
            activeAttempts=self.activeAttempts,
            runtimeKind=config.detectRuntimeKind(),
        )
        payload = message.model_dump(mode="json")
        for baseUrl in self.coordinatorBaseUrls:
            try:
                response = await client.post(f"{baseUrl}/heartbeat", json=payload, timeout=2.0)
                if response.status_code == 200:
                    return True
            except httpx.HTTPError:
                continue
        logger.warning("worker %s could not reach any coordinator for heartbeat", self.workerId)
        return False

    async def heartbeatLoop(self) -> None:
        async with httpx.AsyncClient() as client:
            while True:
                await self.heartbeatOnce(client)
                await asyncio.sleep(config.heartbeatIntervalSeconds())


async def executeCapability(
    runtime: WorkerRuntime,
    capabilities: dict[str, CapabilityHandler],
    requestId: UUID,
    runId: UUID,
    ticker: str,
    capability: str,
    lamportTimestamp: int,
    timeoutSeconds: float,
) -> WorkerResponse:
    handler = capabilities.get(capability)
    if handler is None:
        raise KeyError(capability)
    runtime.clock.observe(lamportTimestamp)
    runtime.activeAttempts += 1
    startedAt = datetime.now(timezone.utc)
    loop = asyncio.get_running_loop()
    try:
        evidence = await asyncio.wait_for(
            loop.run_in_executor(runtime.executor, handler, ticker),
            timeout=timeoutSeconds,
        )
        status = AttemptStatus.success if any(item.status == "ok" for item in evidence) else AttemptStatus.partial
        error = None
    except asyncio.TimeoutError:
        evidence = []
        status = AttemptStatus.timeout
        error = {"message": f"{capability} exceeded {timeoutSeconds}s"}
    except Exception as caught:
        evidence = []
        status = AttemptStatus.failed
        error = {"message": str(caught), "type": type(caught).__name__}
    finally:
        runtime.activeAttempts -= 1
    completedAt = datetime.now(timezone.utc)
    return WorkerResponse(
        requestId=requestId,
        runId=runId,
        workerId=runtime.workerId,
        workerGroup=runtime.group,
        capability=capability,
        status=status,
        startedAt=startedAt,
        completedAt=completedAt,
        latencyMs=(completedAt - startedAt).total_seconds() * 1000.0,
        evidence=evidence,
        error=error,
        lamportTimestamp=runtime.clock.tick(),
    )


def evidenceToProto(item: EvidenceRecord) -> worker_pb2.EvidenceRecord:
    return worker_pb2.EvidenceRecord(
        vendor=item.vendor,
        capability=item.capability,
        status=item.status,
        latency_ms=item.latencyMs or 0.0,
        observed_at=item.observedAt.isoformat() if item.observedAt else "",
        data_json=json.dumps(item.data) if item.data is not None else "",
        error=item.error or "",
    )


class CapabilityServicer(worker_pb2_grpc.WorkerCapabilityServicer):
    def __init__(self, runtime: WorkerRuntime, capabilities: dict[str, CapabilityHandler]) -> None:
        self.runtime = runtime
        self.capabilities = capabilities

    async def ExecuteCapability(
        self, request: worker_pb2.CapabilityRequest, context: grpc.aio.ServicerContext
    ) -> worker_pb2.CapabilityResponse:
        if request.capability not in self.capabilities:
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                f"capability {request.capability} not served by {self.runtime.workerId}",
            )
        try:
            requestId = UUID(request.request_id)
            runId = UUID(request.run_id)
        except ValueError as caught:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(caught))
        timeoutSeconds = request.timeout_seconds if request.timeout_seconds > 0 else 15.0
        try:
            response = await asyncio.wait_for(
                executeCapability(
                    self.runtime,
                    self.capabilities,
                    requestId,
                    runId,
                    request.ticker,
                    request.capability,
                    request.lamport_timestamp,
                    timeoutSeconds,
                ),
                timeout=timeoutSeconds + 2.0,
            )
        except asyncio.TimeoutError:
            await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, f"{request.capability} exceeded its RPC deadline")
        return worker_pb2.CapabilityResponse(
            request_id=str(response.requestId),
            run_id=str(response.runId),
            worker_id=response.workerId,
            worker_group=response.workerGroup.value,
            capability=response.capability,
            status=response.status.value,
            started_at=response.startedAt.isoformat(),
            completed_at=response.completedAt.isoformat(),
            latency_ms=response.latencyMs,
            evidence=[evidenceToProto(item) for item in response.evidence],
            error_json=json.dumps(response.error) if response.error else "",
            lamport_timestamp=response.lamportTimestamp,
        )


def createWorkerApp(workerId: str, group: WorkerGroup, capabilities: dict[str, CapabilityHandler]) -> FastAPI:
    runtime = WorkerRuntime(
        workerId=workerId,
        group=group,
        host=config.workerHost(),
        port=config.workerPort(),
        coordinatorBaseUrls=[url.strip() for url in config.envText("COORDINATOR_BASE_URLS", config.coordinatorBaseUrl()).split(",") if url.strip()],
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        heartbeatTask = asyncio.create_task(runtime.heartbeatLoop())
        grpcServer = grpc.aio.server(ThreadPoolExecutor(max_workers=8))
        worker_pb2_grpc.add_WorkerCapabilityServicer_to_server(CapabilityServicer(runtime, capabilities), grpcServer)
        grpcServer.add_insecure_port(f"0.0.0.0:{config.grpcPort()}")
        await grpcServer.start()
        try:
            yield
        finally:
            heartbeatTask.cancel()
            await grpcServer.stop(grace=5.0)

    app = FastAPI(title=f"OmniSignal distributed worker — {workerId}", lifespan=lifespan)
    app.state.runtime = runtime

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "workerId": workerId,
            "group": group.value,
            "status": "ok",
            "lamportTimestamp": runtime.clock.peek(),
            "activeAttempts": runtime.activeAttempts,
            "grpcPort": config.grpcPort(),
        }

    @app.post("/capability", response_model=WorkerResponse)
    async def handleCapability(request: CapabilityRequest) -> WorkerResponse:
        if request.capability not in capabilities:
            raise HTTPException(status_code=404, detail=f"capability {request.capability} not served by {workerId}")
        return await executeCapability(
            runtime,
            capabilities,
            request.requestId,
            request.runId,
            request.ticker,
            request.capability,
            request.lamportTimestamp,
            request.timeoutSeconds,
        )

    return app
