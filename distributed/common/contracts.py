from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WorkerGroup(str, Enum):
    market = "market"
    fundamentals = "fundamentals"
    news_macro = "news_macro"


class CoordinatorRole(str, Enum):
    leader = "leader"
    standby = "standby"
    recovering = "recovering"
    unavailable = "unavailable"
    unknown = "unknown"


class WorkerHealth(str, Enum):
    healthy = "healthy"
    suspected = "suspected"
    recovering = "recovering"
    unavailable = "unavailable"


class RunState(str, Enum):
    created = "created"
    dispatched = "dispatched"
    running = "running"
    partially_completed = "partially_completed"
    completed = "completed"
    failed = "failed"
    recovering = "recovering"


class AttemptStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    partial = "partial"
    timeout = "timeout"
    failed = "failed"


class LamportStamp(BaseModel):
    processId: str
    counter: int


class ProtocolEvent(BaseModel):
    processId: str
    processRole: str
    eventType: str
    lamportTimestamp: int
    wallClock: datetime
    runId: Optional[UUID] = None
    requestId: Optional[UUID] = None
    detail: dict[str, Any] = Field(default_factory=dict)


class BeaconMessage(BaseModel):
    senderId: str
    senderRole: CoordinatorRole
    epoch: int
    lamportTimestamp: int
    sentAt: datetime
    knownLeaderId: Optional[str] = None


class HeartbeatMessage(BaseModel):
    workerId: str
    workerGroup: WorkerGroup
    sequence: int
    host: str
    port: int
    lamportTimestamp: int
    sentAt: datetime
    activeAttempts: int = 0
    runtimeKind: str = "unknown"


class CapabilityRequest(BaseModel):
    requestId: UUID
    runId: UUID
    ticker: str
    capability: str
    leaderEpoch: int
    lamportTimestamp: int
    coordinatorId: str
    timeoutSeconds: float = 15.0


class EvidenceRecord(BaseModel):
    vendor: str
    capability: str
    status: str
    latencyMs: Optional[float] = None
    observedAt: Optional[datetime] = None
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class WorkerResponse(BaseModel):
    requestId: UUID
    runId: UUID
    workerId: str
    workerGroup: WorkerGroup
    capability: str
    status: AttemptStatus
    startedAt: datetime
    completedAt: datetime
    latencyMs: float
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    error: Optional[dict[str, Any]] = None
    lamportTimestamp: int


class RunDispatchBody(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    capabilities: list[str] = Field(default_factory=lambda: ["quote", "fundamentals", "news"])


class RunRecord(BaseModel):
    id: UUID
    ticker: str
    state: RunState
    createdAt: datetime
    updatedAt: datetime
    leaderEpoch: int
    generation: int
    result: Optional[dict[str, Any]] = None


class WorkerAttemptRecord(BaseModel):
    id: UUID
    runId: UUID
    workerGroup: WorkerGroup
    workerId: str
    capability: str
    status: AttemptStatus
    startedAt: datetime
    completedAt: Optional[datetime] = None
    latencyMs: Optional[float] = None
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    error: Optional[dict[str, Any]] = None


class CoordinatorInfo(BaseModel):
    id: str
    host: str
    port: int
    role: CoordinatorRole
    epoch: int
    lamportTimestamp: int
    lastBeaconSentAt: Optional[datetime] = None
    lastBeaconFromLeaderAt: Optional[datetime] = None
    registeredAt: datetime
    runtimeKind: str = "unknown"
    runtimeRef: Optional[str] = None


class WorkerInfo(BaseModel):
    id: str
    group: WorkerGroup
    host: str
    port: int
    status: WorkerHealth
    lastHeartbeatAt: Optional[datetime] = None
    lastSequence: int = 0
    activeAttempts: int = 0
    runtimeKind: str = "unknown"
    runtimeRef: Optional[str] = None


class OperatorActionResult(BaseModel):
    actor: str
    action: str
    target: str
    accepted: bool
    result: str
    detail: dict[str, Any] = Field(default_factory=dict)
