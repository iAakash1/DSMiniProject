from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from distributed.common import config, database
from distributed.common.migrate import ensureSchema
from distributed.control_api.runtimeadapter import UnsupportedAdapter


def buildAdapter():
    if config.dockerAdapterEnabled():
        from distributed.control_api.dockeradapter import DockerAdapter

        return DockerAdapter(config.dockerComposeProject())
    if config.kubernetesAdapterEnabled():
        from distributed.control_api.kubernetesadapter import KubernetesAdapter

        return KubernetesAdapter(config.kubernetesNamespace())
    return UnsupportedAdapter()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    pool = await database.openPool(config.databaseUrl())
    await ensureSchema(pool)
    app.state.adapter = buildAdapter()
    try:
        yield
    finally:
        await database.closePool()


app = FastAPI(title="OmniSignal distributed control API", lifespan=lifespan)

allowedOrigins = [origin.strip() for origin in config.envText("CONTROL_API_ALLOWED_ORIGINS", "http://localhost:3100").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowedOrigins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["authorization", "content-type"],
)


def parseJsonFields(row: Any, fields: list[str]) -> dict[str, Any]:
    parsed = dict(row)
    for field in fields:
        value = parsed.get(field)
        if isinstance(value, str):
            try:
                parsed[field] = json.loads(value)
            except json.JSONDecodeError:
                pass
    return parsed


def requireOperator(authorization: str = Header(default="")) -> str:
    expected = config.envText("CONTROL_API_OPERATOR_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="no operator token is configured — lifecycle actions are disabled")
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    if token != expected:
        raise HTTPException(status_code=403, detail="invalid operator token")
    return "operator"


async def recordOperatorAction(actor: str, action: str, target: str, accepted: bool, result: str, detail: dict[str, Any]) -> None:
    await database.execute(
        "insert into operator_actions (actor, action, target, accepted, result, detail) values ($1, $2, $3, $4, $5, $6)",
        actor, action, target, accepted, result, json.dumps(detail),
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "runtime": app.state.adapter.kind}


@app.get("/coordinators")
async def listCoordinators() -> dict:
    rows = await database.fetchAll("select * from coordinators order by id")
    return {"coordinators": [dict(row) for row in rows]}


@app.get("/coordinators/{coordinatorId}")
async def getCoordinator(coordinatorId: str) -> dict:
    row = await database.fetchOne("select * from coordinators where id = $1", coordinatorId)
    if row is None:
        raise HTTPException(status_code=404, detail="coordinator not found")
    recentEvents = await database.fetchAll(
        "select * from protocol_events where process_id = $1 order by wall_clock desc limit 50", coordinatorId
    )
    return {"coordinator": dict(row), "recentEvents": [parseJsonFields(event, ["detail"]) for event in recentEvents]}


@app.get("/workers")
async def listWorkers() -> dict:
    rows = await database.fetchAll("select * from workers order by worker_group, id")
    return {"workers": [dict(row) for row in rows]}


@app.get("/runs")
async def listRuns(limit: int = 50) -> dict:
    rows = await database.fetchAll("select * from research_runs order by created_at desc limit $1", limit)
    return {"runs": [parseJsonFields(row, ["capabilities", "result"]) for row in rows]}


@app.get("/runs/{runId}")
async def getRun(runId: str) -> dict:
    row = await database.fetchOne("select * from research_runs where id = $1", runId)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    attempts = await database.fetchAll("select * from worker_attempts where run_id = $1 order by started_at", runId)
    runEvents = await database.fetchAll("select * from protocol_events where run_id = $1 order by wall_clock", runId)
    return {
        "run": parseJsonFields(row, ["capabilities", "result"]),
        "attempts": [parseJsonFields(attempt, ["evidence", "error"]) for attempt in attempts],
        "events": [parseJsonFields(event, ["detail"]) for event in runEvents],
    }


class DispatchRunBody(BaseModel):
    ticker: str
    capabilities: list[str]


@app.post("/runs")
async def dispatchRunThroughLeader(body: DispatchRunBody) -> dict:
    leaderRow = await database.fetchOne("select host, port from coordinators where role = 'leader' limit 1")
    if leaderRow is None:
        raise HTTPException(status_code=503, detail="no leader is currently elected")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"http://{leaderRow['host']}:{leaderRow['port']}/runs",
                json=body.model_dump(),
                timeout=20.0,
            )
        except httpx.HTTPError as error:
            raise HTTPException(status_code=502, detail=f"leader unreachable: {error}")
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    return response.json()


@app.get("/events")
async def listEvents(
    processId: Optional[str] = None,
    eventType: Optional[str] = None,
    runId: Optional[str] = None,
    limit: int = 100,
) -> dict:
    clauses = []
    args: list[Any] = []
    if processId:
        args.append(processId)
        clauses.append(f"process_id = ${len(args)}")
    if eventType:
        args.append(eventType)
        clauses.append(f"event_type = ${len(args)}")
    if runId:
        args.append(runId)
        clauses.append(f"run_id = ${len(args)}")
    where = f"where {' and '.join(clauses)}" if clauses else ""
    args.append(limit)
    rows = await database.fetchAll(
        f"select * from protocol_events {where} order by id desc limit ${len(args)}", *args
    )
    return {"events": [parseJsonFields(row, ["detail"]) for row in rows]}


@app.get("/topology")
async def topology() -> dict:
    coordinators = await database.fetchAll("select id, host, port, role, epoch from coordinators")
    workers = await database.fetchAll("select id, worker_group, host, port, status, last_heartbeat_receiver_id from workers")
    controlApiId = "control-api"
    nodes = [
        {"id": controlApiId, "kind": "control-api", "status": "healthy"},
    ] + [
        {"id": row["id"], "kind": "coordinator", "role": row["role"], "epoch": row["epoch"]}
        for row in coordinators
    ] + [
        {"id": row["id"], "kind": "worker", "group": row["worker_group"], "status": row["status"]}
        for row in workers
    ]
    coordinatorIds = sorted(row["id"] for row in coordinators)
    edges = [
        {"source": coordinatorIds[i], "target": coordinatorIds[j], "kind": "beacon_mesh"}
        for i in range(len(coordinatorIds))
        for j in range(i + 1, len(coordinatorIds))
    ]
    edges += [{"source": controlApiId, "target": coordinatorId, "kind": "control_link"} for coordinatorId in coordinatorIds]
    coordinatorIdSet = set(coordinatorIds)
    for row in workers:
        if row["last_heartbeat_receiver_id"] and row["last_heartbeat_receiver_id"] in coordinatorIdSet:
            edges.append({"source": row["last_heartbeat_receiver_id"], "target": row["id"], "kind": "heartbeat"})
    return {"nodes": nodes, "edges": edges}


class LifecycleActionBody(BaseModel):
    role: str = "coordinator"


@app.post("/coordinators/{instanceId}/stop")
async def stopCoordinator(instanceId: str, actor: str = Depends(requireOperator)) -> dict:
    outcome = await app.state.adapter.stopInstance(instanceId)
    await recordOperatorAction(actor, "stop", instanceId, outcome["accepted"], outcome["result"], outcome.get("detail", {}))
    return outcome


@app.post("/coordinators/{instanceId}/restart")
async def restartCoordinator(instanceId: str, actor: str = Depends(requireOperator)) -> dict:
    outcome = await app.state.adapter.restartInstance(instanceId)
    await recordOperatorAction(actor, "restart", instanceId, outcome["accepted"], outcome["result"], outcome.get("detail", {}))
    return outcome


@app.post("/coordinators/{instanceId}/delete")
async def deleteCoordinator(instanceId: str, actor: str = Depends(requireOperator)) -> dict:
    outcome = await app.state.adapter.deleteInstance(instanceId)
    await recordOperatorAction(actor, "delete", instanceId, outcome["accepted"], outcome["result"], outcome.get("detail", {}))
    if outcome["accepted"]:
        await database.execute("delete from coordinators where id = $1", instanceId)
    return outcome


@app.post("/coordinators")
async def addCoordinator(body: LifecycleActionBody, actor: str = Depends(requireOperator)) -> dict:
    outcome = await app.state.adapter.addInstance(body.role)
    await recordOperatorAction(actor, "add", body.role, outcome["accepted"], outcome["result"], outcome.get("detail", {}))
    return outcome


@app.get("/events/stream")
async def streamEvents() -> StreamingResponse:
    async def generator():
        lastId = 0
        row = await database.fetchOne("select max(id) as max_id from protocol_events")
        if row is not None and row["max_id"] is not None:
            lastId = row["max_id"]
        while True:
            rows = await database.fetchAll("select * from protocol_events where id > $1 order by id limit 100", lastId)
            for eventRow in rows:
                lastId = eventRow["id"]
                payload = {
                    key: (value.isoformat() if isinstance(value, datetime) else value)
                    for key, value in parseJsonFields(eventRow, ["detail"]).items()
                }
                yield f"data: {json.dumps(payload, default=str)}\n\n"
            if not rows:
                yield ": keep-alive\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(generator(), media_type="text/event-stream")
