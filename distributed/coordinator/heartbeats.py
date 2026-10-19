from __future__ import annotations

from datetime import datetime, timezone

from distributed.common import database, events
from distributed.common.contracts import HeartbeatMessage, WorkerHealth
from distributed.common.lamportclock import LamportClock


async def recordHeartbeat(message: HeartbeatMessage, clock: LamportClock, receiverId: str) -> None:
    clock.observe(message.lamportTimestamp)
    await database.execute(
        """
        insert into workers (id, worker_group, host, port, status, last_heartbeat_at, last_heartbeat_receiver_id, last_sequence, active_attempts, runtime_kind, runtime_ref)
        values ($1, $2, $3, $4, $5, now(), $6, $7, $8, $9, $1)
        on conflict (id) do update set
            worker_group = excluded.worker_group,
            host = excluded.host,
            port = excluded.port,
            status = excluded.status,
            last_heartbeat_at = excluded.last_heartbeat_at,
            last_heartbeat_receiver_id = excluded.last_heartbeat_receiver_id,
            last_sequence = excluded.last_sequence,
            active_attempts = excluded.active_attempts,
            runtime_kind = excluded.runtime_kind
        """,
        message.workerId,
        message.workerGroup.value,
        message.host,
        message.port,
        WorkerHealth.healthy.value,
        receiverId,
        message.sequence,
        message.activeAttempts,
        message.runtimeKind,
    )
    await events.recordEvent(
        receiverId, "coordinator", "heartbeat_received", clock.tick(),
        detail={"workerId": message.workerId, "group": message.workerGroup.value, "sequence": message.sequence},
    )


async def sweepWorkerHealth(heartbeatIntervalSeconds: float, missedThreshold: int, receiverId: str, clock: LamportClock) -> None:
    suspectDeadline = heartbeatIntervalSeconds * missedThreshold
    unavailableDeadline = suspectDeadline * 2
    rows = await database.fetchAll("select id, status, last_heartbeat_at from workers")
    now = datetime.now(timezone.utc)
    for row in rows:
        lastHeartbeat = row["last_heartbeat_at"]
        if lastHeartbeat is None:
            continue
        elapsed = (now - lastHeartbeat).total_seconds()
        if elapsed <= suspectDeadline:
            nextStatus = WorkerHealth.healthy
        elif elapsed <= unavailableDeadline:
            nextStatus = WorkerHealth.suspected
        else:
            nextStatus = WorkerHealth.unavailable
        if nextStatus.value != row["status"]:
            await database.execute("update workers set status = $2 where id = $1", row["id"], nextStatus.value)
            await events.recordEvent(
                receiverId, "coordinator", "worker_health_changed", clock.tick(),
                detail={"workerId": row["id"], "from": row["status"], "to": nextStatus.value, "elapsedSeconds": elapsed},
            )
