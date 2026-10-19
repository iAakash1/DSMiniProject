from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx


class RemoteCallError(Exception):
    def __init__(self, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


async def postJson(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    correlationId: str,
    timeoutSeconds: float = 5.0,
    maxAttempts: int = 3,
) -> dict[str, Any]:
    headers = {"x-correlation-id": correlationId}
    lastError: Optional[Exception] = None
    for attempt in range(1, maxAttempts + 1):
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=timeoutSeconds)
            if response.status_code >= 500 and attempt < maxAttempts:
                lastError = RemoteCallError(f"{url} returned {response.status_code}", retryable=True)
                await asyncio.sleep(0.2 * attempt)
                continue
            response.raise_for_status()
            return response.json()
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as error:
            lastError = RemoteCallError(f"{url} unreachable: {error}", retryable=True)
            if attempt < maxAttempts:
                await asyncio.sleep(0.2 * attempt)
                continue
    raise lastError if lastError else RemoteCallError(f"{url} failed with no attempts", retryable=False)


async def getJson(
    client: httpx.AsyncClient,
    url: str,
    correlationId: str,
    timeoutSeconds: float = 5.0,
) -> dict[str, Any]:
    headers = {"x-correlation-id": correlationId}
    response = await client.get(url, headers=headers, timeout=timeoutSeconds)
    response.raise_for_status()
    return response.json()
