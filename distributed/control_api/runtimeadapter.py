from __future__ import annotations

from typing import Any, Protocol


class RuntimeAdapter(Protocol):
    kind: str

    async def listManagedInstances(self, role: str) -> list[dict[str, Any]]: ...

    async def stopInstance(self, instanceId: str) -> dict[str, Any]: ...

    async def restartInstance(self, instanceId: str) -> dict[str, Any]: ...

    async def deleteInstance(self, instanceId: str) -> dict[str, Any]: ...

    async def addInstance(self, role: str) -> dict[str, Any]: ...


class UnsupportedAdapter:
    kind = "unsupported"

    async def listManagedInstances(self, role: str) -> list[dict[str, Any]]:
        return []

    async def stopInstance(self, instanceId: str) -> dict[str, Any]:
        return self.refusal("stop", instanceId)

    async def restartInstance(self, instanceId: str) -> dict[str, Any]:
        return self.refusal("restart", instanceId)

    async def deleteInstance(self, instanceId: str) -> dict[str, Any]:
        return self.refusal("delete", instanceId)

    async def addInstance(self, role: str) -> dict[str, Any]:
        return self.refusal("add", role)

    def refusal(self, action: str, target: str) -> dict[str, Any]:
        return {
            "accepted": False,
            "result": "unsupported_runtime",
            "detail": {
                "message": f"no runtime adapter is configured — {action} on {target} cannot affect any real process",
            },
        }
