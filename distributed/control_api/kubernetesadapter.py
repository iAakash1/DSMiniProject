from __future__ import annotations

from typing import Any

from kubernetes import client, config as kubeConfig

ROLE_LABEL = "com.minialaddin.distributed/role"

ROLE_STATEFULSET = {
    "coordinator": "coordinator",
    "market": "worker-market",
    "fundamentals": "worker-fundamentals",
    "news_macro": "worker-news-macro",
}


class KubernetesAdapter:
    kind = "kubernetes"

    def __init__(self, namespace: str) -> None:
        try:
            kubeConfig.load_incluster_config()
        except kubeConfig.ConfigException:
            kubeConfig.load_kube_config()
        self.namespace = namespace
        self.coreApi = client.CoreV1Api()
        self.appsApi = client.AppsV1Api()

    async def listManagedInstances(self, role: str) -> list[dict[str, Any]]:
        pods = self.coreApi.list_namespaced_pod(self.namespace, label_selector=f"{ROLE_LABEL}={role}")
        return [
            {
                "instanceId": pod.metadata.name,
                "status": pod.status.phase,
                "runtimeKind": self.kind,
                "node": pod.spec.node_name,
            }
            for pod in pods.items
        ]

    async def stopInstance(self, instanceId: str) -> dict[str, Any]:
        return {
            "accepted": False,
            "result": "unsupported_operation",
            "detail": {
                "message": "stop is not supported for StatefulSet-backed coordinators in Kubernetes — delete decreases the replica count instead",
            },
        }

    async def restartInstance(self, instanceId: str) -> dict[str, Any]:
        try:
            self.coreApi.delete_namespaced_pod(instanceId, self.namespace)
        except client.ApiException as error:
            return {"accepted": False, "result": "api_error", "detail": {"status": error.status, "reason": error.reason}}
        return {"accepted": True, "result": "restarted", "detail": {"instanceId": instanceId, "note": "pod deleted; the StatefulSet controller recreates it"}}

    async def deleteInstance(self, instanceId: str) -> dict[str, Any]:
        statefulSetName = instanceId.rsplit("-", 1)[0]
        try:
            statefulSet = self.appsApi.read_namespaced_stateful_set(statefulSetName, self.namespace)
            currentReplicas = statefulSet.spec.replicas or 1
            if currentReplicas <= 1:
                return {
                    "accepted": False,
                    "result": "refused",
                    "detail": {"message": "refusing to scale a StatefulSet to zero replicas through this action"},
                }
            self.appsApi.patch_namespaced_stateful_set_scale(
                statefulSetName, self.namespace, {"spec": {"replicas": currentReplicas - 1}}
            )
        except client.ApiException as error:
            return {"accepted": False, "result": "api_error", "detail": {"status": error.status, "reason": error.reason}}
        return {"accepted": True, "result": "scaled_down", "detail": {"statefulSet": statefulSetName, "replicas": currentReplicas - 1}}

    async def addInstance(self, role: str) -> dict[str, Any]:
        statefulSetName = ROLE_STATEFULSET.get(role)
        if statefulSetName is None:
            return {"accepted": False, "result": "unknown_role", "detail": {"role": role}}
        try:
            statefulSet = self.appsApi.read_namespaced_stateful_set(statefulSetName, self.namespace)
            currentReplicas = statefulSet.spec.replicas or 0
            self.appsApi.patch_namespaced_stateful_set_scale(
                statefulSetName, self.namespace, {"spec": {"replicas": currentReplicas + 1}}
            )
        except client.ApiException as error:
            return {"accepted": False, "result": "api_error", "detail": {"status": error.status, "reason": error.reason}}
        return {"accepted": True, "result": "scaled_up", "detail": {"statefulSet": statefulSetName, "replicas": currentReplicas + 1}}
