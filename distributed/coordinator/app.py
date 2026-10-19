from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from uuid import UUID

import httpx
from fastapi import FastAPI, Header, HTTPException

from distributed.common import config, database
from distributed.common.contracts import BeaconMessage, HeartbeatMessage, RunDispatchBody
from distributed.common.lamportclock import LamportClock
from distributed.common.migrate import ensureSchema
from distributed.coordinator import dispatch, heartbeats
from distributed.coordinator.grpcclient import closeAllChannels
from distributed.coordinator.leadership import LeadershipManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("distributed.coordinator.app")

clock = LamportClock(config.coordinatorId())
leadership = LeadershipManager(
    selfId=config.coordinatorId(),
    selfHost=config.coordinatorHost(),
    selfPort=config.coordinatorPort(),
    peers=config.coordinatorPeers(),
    beaconIntervalSeconds=config.beaconIntervalSeconds(),
    beaconMissedThreshold=config.beaconMissedThreshold(),
    clock=clock,
)


async def beaconBroadcastLoop() -> None:
    async with httpx.AsyncClient() as client:
        while True:
            await leadership.broadcastBeaconOnce(client)
            await asyncio.sleep(config.beaconIntervalSeconds())


async def detectionLoop() -> None:
    while True:
        await leadership.detectionCheckOnce()
        await leadership.sweepStaleCoordinators()
        await asyncio.sleep(config.beaconIntervalSeconds())


async def workerHealthSweepLoop() -> None:
    while True:
        await heartbeats.sweepWorkerHealth(
            config.heartbeatIntervalSeconds(), config.heartbeatMissedThreshold(), leadership.selfId, clock
        )
        await asyncio.sleep(config.heartbeatIntervalSeconds())


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    pool = await database.openPool(config.databaseUrl())
    await ensureSchema(pool)
    await leadership.bootstrap()
    backgroundTasks = [
        asyncio.create_task(beaconBroadcastLoop()),
        asyncio.create_task(detectionLoop()),
        asyncio.create_task(workerHealthSweepLoop()),
    ]
    try:
        yield
    finally:
        for task in backgroundTasks:
            task.cancel()
        await closeAllChannels()
        await database.closePool()


app = FastAPI(title=f"OmniSignal distributed coordinator — {config.coordinatorId()}", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"coordinatorId": leadership.selfId, "status": "ok", "role": leadership.role.value}


@app.get("/status")
async def status() -> dict:
    return leadership.snapshot()


@app.post("/beacon")
async def receiveBeacon(message: BeaconMessage) -> dict:
    leadership.handleIncomingBeacon(message)
    await leadership.persistSelfState()
    return {"accepted": True}


@app.post("/heartbeat")
async def receiveHeartbeat(message: HeartbeatMessage) -> dict:
    await heartbeats.recordHeartbeat(message, clock, leadership.selfId)
    return {"accepted": True}


@app.post("/runs")
async def createRun(body: RunDispatchBody, xCorrelationId: Optional[str] = Header(default=None, alias="x-correlation-id")) -> dict:
    try:
        return await dispatch.dispatchRun(leadership, body, xCorrelationId)
    except dispatch.LeaderRequiredError as error:
        raise HTTPException(
            status_code=409,
            detail={"message": "this coordinator is not the leader", "knownLeaderId": error.knownLeaderId},
        )


@app.get("/runs/{runId}")
async def readRun(runId: UUID) -> dict:
    run = await dispatch.getRun(runId)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run
