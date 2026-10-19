from __future__ import annotations

import os

import uvicorn

from distributed.common import config

SERVICE_MODULES = {
    "coordinator": "distributed.coordinator.app:app",
    "worker-market": "distributed.workers.market.app:app",
    "worker-fundamentals": "distributed.workers.fundamentals.app:app",
    "worker-news-macro": "distributed.workers.news_macro.app:app",
    "control-api": "distributed.control_api.app:app",
}


def deriveStatefulSetIdentityIfNeeded() -> None:
    podName = os.environ.get("POD_NAME", "")
    headlessService = os.environ.get("COORDINATOR_HEADLESS_SERVICE", "")
    namespace = os.environ.get("POD_NAMESPACE", "")
    replicaCount = int(os.environ.get("COORDINATOR_REPLICA_COUNT", "0"))
    if not podName or not headlessService or replicaCount == 0:
        return
    ordinal = int(podName.rsplit("-", 1)[1])
    domainSuffix = f".{headlessService}.{namespace}.svc.cluster.local:8000" if namespace else f".{headlessService}:8000"
    os.environ.setdefault("COORDINATOR_ID", f"coordinator-{ordinal:02d}")
    os.environ.setdefault("COORDINATOR_HOST", f"{podName}{domainSuffix.split(':')[0]}")
    os.environ.setdefault(
        "COORDINATOR_PEERS",
        ",".join(
            f"http://{podName.rsplit('-', 1)[0]}-{peerOrdinal}{domainSuffix}"
            for peerOrdinal in range(replicaCount)
            if peerOrdinal != ordinal
        ),
    )


def main() -> None:
    serviceKind = config.envText("DISTRIBUTED_SERVICE_KIND", "")
    target = SERVICE_MODULES.get(serviceKind)
    if target is None:
        raise SystemExit(f"DISTRIBUTED_SERVICE_KIND must be one of {sorted(SERVICE_MODULES)}, got {serviceKind!r}")
    if serviceKind == "coordinator":
        deriveStatefulSetIdentityIfNeeded()
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(target, host="0.0.0.0", port=port, workers=1)


if __name__ == "__main__":
    main()
