from __future__ import annotations

import os
import socket


def envText(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def envInt(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


def envFloat(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value not in (None, "") else default


def envBool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def databaseUrl() -> str:
    return envText(
        "DISTRIBUTED_DATABASE_URL",
        "postgresql://omnisignal:omnisignal@localhost:5532/omnisignal_distributed",
    )


def coordinatorId() -> str:
    return envText("COORDINATOR_ID", "coordinator-01")


def coordinatorHost() -> str:
    return envText("COORDINATOR_HOST", "localhost")


def coordinatorPort() -> int:
    return envInt("COORDINATOR_PORT", 7001)


def coordinatorPeers() -> list[str]:
    return [peer for peer in envText("COORDINATOR_PEERS", "").split(",") if peer]


def beaconIntervalSeconds() -> float:
    return envFloat("BEACON_INTERVAL_SECONDS", 1.0)


def beaconMissedThreshold() -> int:
    return envInt("BEACON_MISSED_THRESHOLD", 3)


def selfContainerAddress() -> str:
    hostname = socket.gethostname()
    try:
        return socket.gethostbyname(hostname)
    except OSError:
        return hostname


def workerId() -> str:
    return envText("WORKER_ID", socket.gethostname())


def workerGroup() -> str:
    return envText("WORKER_GROUP", "market")


def workerHost() -> str:
    return envText("WORKER_HOST", selfContainerAddress())


def workerPort() -> int:
    return envInt("WORKER_PORT", 8101)


def detectRuntimeKind() -> str:
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return "kubernetes"
    if os.path.exists("/.dockerenv"):
        return "docker"
    return "unknown"


def grpcPort() -> int:
    return envInt("GRPC_PORT", 9000)


def coordinatorBaseUrl() -> str:
    return envText("COORDINATOR_BASE_URL", "http://localhost:7001")


def heartbeatIntervalSeconds() -> float:
    return envFloat("HEARTBEAT_INTERVAL_SECONDS", 1.5)


def heartbeatMissedThreshold() -> int:
    return envInt("HEARTBEAT_MISSED_THRESHOLD", 3)


def useTestAdapters() -> bool:
    return envBool("DISTRIBUTED_TEST_ADAPTERS", False)


def controlApiHost() -> str:
    return envText("CONTROL_API_HOST", "0.0.0.0")


def controlApiPort() -> int:
    return envInt("CONTROL_API_PORT", 7900)


def dockerAdapterEnabled() -> bool:
    return envBool("DISTRIBUTED_DOCKER_ADAPTER", False)


def dockerComposeProject() -> str:
    return envText("DISTRIBUTED_COMPOSE_PROJECT", "minialaddin")


def kubernetesAdapterEnabled() -> bool:
    return envBool("DISTRIBUTED_KUBERNETES_ADAPTER", False)


def kubernetesNamespace() -> str:
    return envText("DISTRIBUTED_KUBERNETES_NAMESPACE", "minialaddin-distributed")
