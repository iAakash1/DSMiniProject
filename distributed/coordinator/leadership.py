from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from distributed.common import database, events
from distributed.common.contracts import BeaconMessage, CoordinatorRole
from distributed.common.lamportclock import LamportClock

logger = logging.getLogger("distributed.coordinator.leadership")


class LeadershipManager:
    def __init__(
        self,
        selfId: str,
        selfHost: str,
        selfPort: int,
        peers: list[str],
        beaconIntervalSeconds: float,
        beaconMissedThreshold: int,
        clock: LamportClock,
    ) -> None:
        self.selfId = selfId
        self.selfHost = selfHost
        self.selfPort = selfPort
        self.peers = peers
        self.beaconIntervalSeconds = beaconIntervalSeconds
        self.beaconMissedThreshold = beaconMissedThreshold
        self.clock = clock
        self.role = CoordinatorRole.standby
        self.epoch = 0
        self.knownLeaderId: Optional[str] = None
        self.lastBeaconFromLeaderAt: Optional[datetime] = None
        self.lastBeaconSentAt: Optional[datetime] = None
        self.guard = asyncio.Lock()

    async def bootstrap(self) -> None:
        row = await database.fetchOne("select epoch, leader_id from leadership_state where singleton = true")
        if row is not None:
            self.epoch = row["epoch"]
            self.knownLeaderId = row["leader_id"]
            self.role = CoordinatorRole.leader if row["leader_id"] == self.selfId else CoordinatorRole.standby
        await database.execute(
            """
            insert into coordinators (id, host, port, role, epoch, lamport_timestamp, registered_at, runtime_kind, runtime_ref)
            values ($1, $2, $3, $4, $5, $6, now(), $7, $8)
            on conflict (id) do update set
                host = excluded.host,
                port = excluded.port,
                role = excluded.role,
                epoch = excluded.epoch,
                runtime_kind = excluded.runtime_kind,
                runtime_ref = excluded.runtime_ref
            """,
            self.selfId,
            self.selfHost,
            self.selfPort,
            self.role.value,
            self.epoch,
            self.clock.peek(),
            "docker",
            self.selfId,
        )
        await events.recordEvent(self.selfId, "coordinator", "bootstrap", self.clock.tick(), detail={"epoch": self.epoch, "role": self.role.value})

    async def persistSelfState(self) -> None:
        await database.execute(
            """
            insert into coordinators (id, host, port, role, epoch, lamport_timestamp, last_beacon_sent_at, last_beacon_from_leader_at, last_seen_at, registered_at, runtime_kind, runtime_ref)
            values ($1, $2, $3, $4, $5, $6, $7, $8, now(), now(), $9, $1)
            on conflict (id) do update set
                role = excluded.role,
                epoch = excluded.epoch,
                lamport_timestamp = excluded.lamport_timestamp,
                last_beacon_sent_at = excluded.last_beacon_sent_at,
                last_beacon_from_leader_at = excluded.last_beacon_from_leader_at,
                last_seen_at = excluded.last_seen_at
            """,
            self.selfId,
            self.selfHost,
            self.selfPort,
            self.role.value,
            self.epoch,
            self.clock.peek(),
            self.lastBeaconSentAt,
            self.lastBeaconFromLeaderAt,
            "docker",
        )

    async def sweepStaleCoordinators(self) -> None:
        deadline = self.beaconIntervalSeconds * self.beaconMissedThreshold * 2
        rows = await database.fetchAll(
            "select id, role from coordinators where id != $1 and role != 'unavailable' and last_seen_at < now() - ($2 * interval '1 second')",
            self.selfId,
            deadline,
        )
        for row in rows:
            await database.execute("update coordinators set role = $2 where id = $1", row["id"], CoordinatorRole.unavailable.value)
            await events.recordEvent(
                self.selfId, "coordinator", "peer_marked_unavailable", self.clock.tick(),
                detail={"peerId": row["id"], "previousRole": row["role"]},
            )

    async def attemptTakeover(self) -> bool:
        async with self.guard:
            row = await database.fetchOne(
                """
                update leadership_state set epoch = epoch + 1, leader_id = $1, updated_at = now()
                where singleton = true and epoch = $2
                returning epoch
                """,
                self.selfId,
                self.epoch,
            )
            if row is None:
                refreshed = await database.fetchOne("select epoch, leader_id from leadership_state where singleton = true")
                if refreshed is not None:
                    self.epoch = refreshed["epoch"]
                    self.knownLeaderId = refreshed["leader_id"]
                self.role = CoordinatorRole.standby
                self.lastBeaconFromLeaderAt = datetime.now(timezone.utc)
                await events.recordEvent(
                    self.selfId, "coordinator", "takeover_lost", self.clock.tick(),
                    detail={"epoch": self.epoch, "newLeader": self.knownLeaderId},
                )
                return False
            self.epoch = row["epoch"]
            self.knownLeaderId = self.selfId
            self.role = CoordinatorRole.leader
            await events.recordEvent(
                self.selfId, "coordinator", "takeover_won", self.clock.tick(),
                detail={"epoch": self.epoch},
            )
            await self.persistSelfState()
            return True

    def handleIncomingBeacon(self, message: BeaconMessage) -> None:
        self.clock.observe(message.lamportTimestamp)
        if message.epoch < self.epoch:
            return
        if message.senderRole != CoordinatorRole.leader:
            return
        self.epoch = message.epoch
        self.knownLeaderId = message.senderId
        self.lastBeaconFromLeaderAt = datetime.now(timezone.utc)
        if message.senderId != self.selfId:
            self.role = CoordinatorRole.standby

    async def validateLeadershipOrDemote(self) -> bool:
        if self.role != CoordinatorRole.leader:
            return False
        row = await database.fetchOne("select epoch, leader_id from leadership_state where singleton = true")
        if row is None:
            self.role = CoordinatorRole.recovering
            return False
        if row["leader_id"] != self.selfId or row["epoch"] != self.epoch:
            self.role = CoordinatorRole.standby
            self.epoch = row["epoch"]
            self.knownLeaderId = row["leader_id"]
            await events.recordEvent(self.selfId, "coordinator", "demoted_on_fencing_check", self.clock.tick(), detail={"epoch": self.epoch})
            return False
        return True

    async def broadcastBeaconOnce(self, client: httpx.AsyncClient) -> None:
        if self.role != CoordinatorRole.leader:
            return
        message = BeaconMessage(
            senderId=self.selfId,
            senderRole=self.role,
            epoch=self.epoch,
            lamportTimestamp=self.clock.tick(),
            sentAt=datetime.now(timezone.utc),
            knownLeaderId=self.selfId,
        )
        self.lastBeaconSentAt = message.sentAt
        payload = json.loads(message.model_dump_json())
        for peer in self.peers:
            try:
                await client.post(f"{peer}/beacon", json=payload, timeout=2.0)
            except httpx.HTTPError:
                logger.warning("beacon to %s unreachable", peer)
        await events.recordEvent(self.selfId, "coordinator", "beacon_sent", message.lamportTimestamp, detail={"epoch": self.epoch, "peers": len(self.peers)})
        await self.persistSelfState()

    async def detectionCheckOnce(self) -> None:
        if self.role == CoordinatorRole.leader:
            await self.validateLeadershipOrDemote()
            await self.persistSelfState()
            return
        now = datetime.now(timezone.utc)
        deadline = self.beaconIntervalSeconds * self.beaconMissedThreshold
        if self.lastBeaconFromLeaderAt is None:
            self.lastBeaconFromLeaderAt = now
            await self.persistSelfState()
            return
        elapsed = (now - self.lastBeaconFromLeaderAt).total_seconds()
        if elapsed <= deadline:
            await self.persistSelfState()
            return
        await events.recordEvent(
            self.selfId, "coordinator", "leader_suspected", self.clock.tick(),
            detail={"epoch": self.epoch, "suspectedLeader": self.knownLeaderId, "elapsedSeconds": elapsed},
        )
        won = await self.attemptTakeover()
        if won:
            await events.recordEvent(self.selfId, "coordinator", "leadership_change", self.clock.tick(), detail={"newLeader": self.selfId, "epoch": self.epoch})
        await self.persistSelfState()

    def snapshot(self) -> dict:
        return {
            "id": self.selfId,
            "role": self.role.value,
            "epoch": self.epoch,
            "knownLeaderId": self.knownLeaderId,
            "lamportTimestamp": self.clock.peek(),
            "lastBeaconSentAt": self.lastBeaconSentAt.isoformat() if self.lastBeaconSentAt else None,
            "lastBeaconFromLeaderAt": self.lastBeaconFromLeaderAt.isoformat() if self.lastBeaconFromLeaderAt else None,
        }
