from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from distributed.common import database


async def recordEvent(
    processId: str,
    processRole: str,
    eventType: str,
    lamportTimestamp: int,
    runId: Optional[UUID] = None,
    requestId: Optional[UUID] = None,
    detail: Optional[dict[str, Any]] = None,
) -> None:
    await database.execute(
        """
        insert into protocol_events
            (process_id, process_role, event_type, lamport_timestamp, wall_clock, run_id, request_id, detail)
        values ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        processId,
        processRole,
        eventType,
        lamportTimestamp,
        datetime.now(timezone.utc),
        runId,
        requestId,
        json.dumps(detail or {}),
    )
