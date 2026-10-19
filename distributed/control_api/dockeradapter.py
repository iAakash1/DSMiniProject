from __future__ import annotations

from typing import Any

import docker
from docker.errors import NotFound

MANAGED_LABEL = "com.minialaddin.distributed.managed"
ROLE_LABEL = "com.minialaddin.distributed.role"
ID_LABEL = "com.minialaddin.distributed.id"


class DockerAdapter:
    kind = "docker"

    def __init__(self, composeProject: str) -> None:
        self.client = docker.from_env()
        self.composeProject = composeProject

    def isManaged(self, container: Any) -> bool:
        labels = container.labels or {}
        return labels.get(MANAGED_LABEL) == "true"

    async def listManagedInstances(self, role: str) -> list[dict[str, Any]]:
        containers = self.client.containers.list(all=True, filters={"label": f"{ROLE_LABEL}={role}"})
        return [
            {
                "instanceId": container.labels.get(ID_LABEL, container.name),
                "containerId": container.id,
                "containerName": container.name,
                "status": container.status,
                "runtimeKind": self.kind,
            }
            for container in containers
            if self.isManaged(container)
        ]

    def findContainer(self, instanceId: str):
        containers = self.client.containers.list(all=True, filters={"label": f"{ID_LABEL}={instanceId}"})
        managed = [container for container in containers if self.isManaged(container)]
        return managed[0] if managed else None

    async def stopInstance(self, instanceId: str) -> dict[str, Any]:
        container = self.findContainer(instanceId)
        if container is None:
            return {"accepted": False, "result": "not_found", "detail": {"instanceId": instanceId}}
        container.stop(timeout=10)
        return {"accepted": True, "result": "stopped", "detail": {"instanceId": instanceId}}

    async def restartInstance(self, instanceId: str) -> dict[str, Any]:
        container = self.findContainer(instanceId)
        if container is None:
            return {"accepted": False, "result": "not_found", "detail": {"instanceId": instanceId}}
        container.restart(timeout=10)
        return {"accepted": True, "result": "restarted", "detail": {"instanceId": instanceId}}

    async def deleteInstance(self, instanceId: str) -> dict[str, Any]:
        container = self.findContainer(instanceId)
        if container is None:
            return {"accepted": False, "result": "not_found", "detail": {"instanceId": instanceId}}
        role = container.labels.get(ROLE_LABEL, "")
        if role == "coordinator":
            siblings = await self.listManagedInstances("coordinator")
            if len(siblings) <= 1:
                return {
                    "accepted": False,
                    "result": "last_coordinator_protected",
                    "detail": {
                        "instanceId": instanceId,
                        "message": "refusing to delete the last managed coordinator — this would permanently destroy the beacon mesh with no template left to add from. Use stop for a reversible fault-injection test instead.",
                    },
                }
        try:
            container.remove(force=True)
        except NotFound:
            pass
        return {"accepted": True, "result": "deleted", "detail": {"instanceId": instanceId}}

    async def addInstance(self, role: str) -> dict[str, Any]:
        if role == "coordinator":
            return {
                "accepted": False,
                "result": "unsupported_static_peers",
                "detail": {
                    "message": "adding a coordinator is disabled: COORDINATOR_PEERS is a static, per-process list read once at startup. A cloned instance would not be in the existing coordinators' peer lists (so the real leader would never beacon to it) while the new instance could still attempt a takeover against a healthy leader — a genuine split-brain risk under the current Beacon implementation, not a cosmetic limitation. Safe dynamic coordinator membership needs peer discovery sourced from the shared database rather than a static env var, which is out of scope here.",
                },
            }
        templates = self.client.containers.list(all=True, filters={"label": f"{ROLE_LABEL}={role}"})
        managedTemplates = [container for container in templates if self.isManaged(container)]
        if not managedTemplates:
            return {
                "accepted": False,
                "result": "no_template",
                "detail": {"message": f"no existing {role} container to clone from"},
            }
        template = managedTemplates[0]
        existingIds = {container.labels.get(ID_LABEL, "") for container in managedTemplates}
        suffix = 1
        while f"{role}-{suffix:02d}" in existingIds:
            suffix += 1
        newInstanceId = f"{role}-{suffix:02d}"
        config = template.attrs["Config"]
        hostConfig = template.attrs["HostConfig"]
        env = [entry for entry in config.get("Env", []) if not entry.startswith(("COORDINATOR_ID=", "COORDINATOR_PORT=", "WORKER_ID=", "WORKER_PORT="))]
        basePort = int(config.get("Labels", {}).get("com.minialaddin.distributed.baseport", "7001"))
        newPort = basePort + suffix
        if role == "coordinator":
            env.append(f"COORDINATOR_ID={newInstanceId}")
            env.append(f"COORDINATOR_PORT={newPort}")
        else:
            env.append(f"WORKER_ID={newInstanceId}")
            env.append(f"WORKER_PORT={newPort}")
        newLabels = dict(config.get("Labels", {}))
        newLabels[ID_LABEL] = newInstanceId
        networkName = next(iter(template.attrs["NetworkSettings"]["Networks"]), None)
        created = self.client.containers.run(
            image=config["Image"],
            name=f"{self.composeProject}-{newInstanceId}",
            environment=env,
            labels=newLabels,
            network=networkName,
            detach=True,
        )
        return {
            "accepted": True,
            "result": "added",
            "detail": {"instanceId": newInstanceId, "containerId": created.id},
        }
