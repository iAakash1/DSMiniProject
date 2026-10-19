from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from distributed.common import database, events
from distributed.common.contracts import (
    AttemptStatus,
    CapabilityRequest,
    RunDispatchBody,
    RunState,
    WorkerGroup,
)
from distributed.coordinator.grpcclient import callWorkerCapability
from distributed.coordinator.leadership import LeadershipManager

logger = logging.getLogger("distributed.coordinator.dispatch")

CAPABILITY_GROUP: dict[str, WorkerGroup] = {
    "quote": WorkerGroup.market,
    "history": WorkerGroup.market,
    "fundamentals": WorkerGroup.fundamentals,
    "company": WorkerGroup.fundamentals,
    "news": WorkerGroup.news_macro,
    "macro": WorkerGroup.news_macro,
}


def parseIsoTimestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class LeaderRequiredError(Exception):
    def __init__(self, knownLeaderId: Optional[str]) -> None:
        super().__init__("this coordinator is not the leader")
        self.knownLeaderId = knownLeaderId


async def pickHealthyWorkers(group: WorkerGroup, limit: int = 3) -> list[dict]:
    rows = await database.fetchAll(
        """
        select id, host, port from workers
        where worker_group = $1 and status = 'healthy'
        order by last_heartbeat_at desc
        limit $2
        """,
        group.value,
        limit,
    )
    return [dict(row) for row in rows]


async def dispatchRun(leadership: LeadershipManager, body: RunDispatchBody, correlationId: Optional[str] = None) -> dict:
    if leadership.role.value != "leader":
        raise LeaderRequiredError(leadership.knownLeaderId)
    if not await leadership.validateLeadershipOrDemote():
        raise LeaderRequiredError(leadership.knownLeaderId)

    runId = uuid4()
    now = datetime.now(timezone.utc)
    await database.execute(
        """
        insert into research_runs (id, ticker, state, created_at, updated_at, leader_epoch, generation, capabilities)
        values ($1, $2, $3, $4, $4, $5, 1, $6)
        """,
        runId,
        body.ticker.upper(),
        RunState.created.value,
        now,
        leadership.epoch,
        json.dumps(body.capabilities),
    )
    await events.recordEvent(
        leadership.selfId, "coordinator", "run_created", leadership.clock.tick(),
        runId=runId, detail={"ticker": body.ticker, "correlationId": correlationId},
    )

    await database.execute("update research_runs set state = $2 where id = $1", runId, RunState.dispatched.value)

    await database.execute("update research_runs set state = $2, updated_at = now() where id = $1", runId, RunState.running.value)
    await events.recordEvent(
        leadership.selfId, "coordinator", "run_running", leadership.clock.tick(),
        runId=runId, detail={"leaderEpoch": leadership.epoch, "capabilities": body.capabilities},
    )

    results: dict[str, dict] = {}
    for capability in body.capabilities:
        group = CAPABILITY_GROUP.get(capability)
        if group is None:
            continue
        workers = await pickHealthyWorkers(group)
        attemptOutcome = None
        for worker in workers:
            requestId = uuid4()
            request = CapabilityRequest(
                requestId=requestId,
                runId=runId,
                ticker=body.ticker.upper(),
                capability=capability,
                leaderEpoch=leadership.epoch,
                lamportTimestamp=leadership.clock.tick(),
                coordinatorId=leadership.selfId,
            )
            await events.recordEvent(
                leadership.selfId, "coordinator", "capability_dispatched", request.lamportTimestamp,
                runId=runId, requestId=requestId, detail={"capability": capability, "worker": worker["id"], "transport": "grpc"},
            )
            attemptId = uuid4()
            startedAt = datetime.now(timezone.utc)
            response = await callWorkerCapability(worker, request)
            if response is None:
                await database.execute(
                    """
                    insert into worker_attempts (id, run_id, worker_group, worker_id, capability, status, started_at, completed_at, evidence, error)
                    values ($1, $2, $3, $4, $5, $6, $7, now(), '[]'::jsonb, $8)
                    """,
                    attemptId, runId, group.value, worker["id"], capability, AttemptStatus.failed.value, startedAt,
                    json.dumps({"message": "worker unreachable over gRPC"}),
                )
                await events.recordEvent(
                    leadership.selfId, "coordinator", "capability_attempt_recorded", leadership.clock.tick(),
                    runId=runId, requestId=requestId, detail={"capability": capability, "status": AttemptStatus.failed.value, "worker": worker["id"]},
                )
                continue
            leadership.clock.observe(response.get("lamportTimestamp", 0))
            completedAt = parseIsoTimestamp(response.get("completedAt")) or datetime.now(timezone.utc)
            await database.execute(
                """
                insert into worker_attempts (id, run_id, worker_group, worker_id, capability, status, started_at, completed_at, latency_ms, evidence, error)
                values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                attemptId, runId, group.value, worker["id"], capability, response["status"],
                startedAt, completedAt, response.get("latencyMs"),
                json.dumps(response.get("evidence", [])), json.dumps(response.get("error")) if response.get("error") else None,
            )
            await events.recordEvent(
                leadership.selfId, "coordinator", "capability_attempt_recorded", leadership.clock.tick(),
                runId=runId, requestId=requestId, detail={"capability": capability, "status": response["status"], "worker": worker["id"]},
            )
            if response["status"] in ("success", "partial"):
                attemptOutcome = response
                break
        if attemptOutcome is not None:
            results[capability] = attemptOutcome

    completedCapabilities = len(results)
    totalCapabilities = len(body.capabilities)
    if completedCapabilities == 0:
        finalState = RunState.failed
    elif completedCapabilities < totalCapabilities:
        finalState = RunState.partially_completed
    else:
        finalState = RunState.completed

    publishResult = {
        "ticker": body.ticker.upper(),
        "capabilities": results,
        "completed": completedCapabilities,
        "total": totalCapabilities,
    }

    if not await leadership.validateLeadershipOrDemote():
        await database.execute(
            "update research_runs set state = $2, updated_at = now() where id = $1",
            runId, RunState.recovering.value,
        )
        raise LeaderRequiredError(leadership.knownLeaderId)

    publishedRow = await database.fetchOne(
        """
        update research_runs
        set state = $2, result = $3, generation = generation + 1, updated_at = now()
        where id = $1 and generation = 1
        returning generation
        """,
        runId, finalState.value, json.dumps(publishResult),
    )
    if publishedRow is None:
        logger.warning("run %s publish lost the generation race", runId)

    await events.recordEvent(
        leadership.selfId, "coordinator", "run_published", leadership.clock.tick(),
        runId=runId, detail={"state": finalState.value, "completed": completedCapabilities, "total": totalCapabilities},
    )

    return {
        "runId": str(runId),
        "state": finalState.value,
        "completed": completedCapabilities,
        "total": totalCapabilities,
        "result": publishResult,
    }


async def getRun(runId: UUID) -> Optional[dict]:
    row = await database.fetchOne("select * from research_runs where id = $1", runId)
    if row is None:
        return None
    attempts = await database.fetchAll("select * from worker_attempts where run_id = $1 order by started_at", runId)
    return {
        "id": str(row["id"]),
        "ticker": row["ticker"],
        "state": row["state"],
        "createdAt": row["created_at"].isoformat(),
        "updatedAt": row["updated_at"].isoformat(),
        "leaderEpoch": row["leader_epoch"],
        "generation": row["generation"],
        "result": json.loads(row["result"]) if row["result"] else None,
        "attempts": [
            {
                "id": str(attempt["id"]),
                "workerGroup": attempt["worker_group"],
                "workerId": attempt["worker_id"],
                "capability": attempt["capability"],
                "status": attempt["status"],
                "startedAt": attempt["started_at"].isoformat(),
                "completedAt": attempt["completed_at"].isoformat() if attempt["completed_at"] else None,
                "latencyMs": attempt["latency_ms"],
            }
            for attempt in attempts
        ],
    }
