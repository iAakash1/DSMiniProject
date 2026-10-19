from __future__ import annotations

import json
import logging
from typing import Optional

import grpc

from distributed.common import config
from distributed.common.contracts import CapabilityRequest
from distributed.proto.v1 import worker_pb2, worker_pb2_grpc

logger = logging.getLogger("distributed.coordinator.grpcclient")

_channels: dict[str, grpc.aio.Channel] = {}


def channelFor(host: str) -> grpc.aio.Channel:
    target = f"{host}:{config.grpcPort()}"
    channel = _channels.get(target)
    if channel is None:
        channel = grpc.aio.insecure_channel(target)
        _channels[target] = channel
    return channel


async def closeAllChannels() -> None:
    for channel in _channels.values():
        await channel.close()
    _channels.clear()


async def callWorkerCapability(worker: dict, request: CapabilityRequest) -> Optional[dict]:
    channel = channelFor(worker["host"])
    stub = worker_pb2_grpc.WorkerCapabilityStub(channel)
    protoRequest = worker_pb2.CapabilityRequest(
        request_id=str(request.requestId),
        run_id=str(request.runId),
        ticker=request.ticker,
        capability=request.capability,
        leader_epoch=request.leaderEpoch,
        lamport_timestamp=request.lamportTimestamp,
        coordinator_id=request.coordinatorId,
        timeout_seconds=request.timeoutSeconds,
    )
    try:
        response = await stub.ExecuteCapability(protoRequest, timeout=request.timeoutSeconds + 2.0)
    except grpc.aio.AioRpcError as error:
        logger.warning(
            "worker %s unreachable for capability %s over gRPC: %s (%s)",
            worker["id"], request.capability, error.details(), error.code(),
        )
        return None
    return {
        "lamportTimestamp": response.lamport_timestamp,
        "completedAt": response.completed_at,
        "status": response.status,
        "latencyMs": response.latency_ms,
        "evidence": [
            {
                "vendor": item.vendor,
                "capability": item.capability,
                "status": item.status,
                "latencyMs": item.latency_ms or None,
                "observedAt": item.observed_at or None,
                "data": json.loads(item.data_json) if item.data_json else None,
                "error": item.error or None,
            }
            for item in response.evidence
        ],
        "error": json.loads(response.error_json) if response.error_json else None,
    }
