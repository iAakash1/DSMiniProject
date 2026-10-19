from __future__ import annotations

from typing import Any, Optional

import asyncpg

pool: Optional[asyncpg.Pool] = None


async def openPool(databaseUrl: str) -> asyncpg.Pool:
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(databaseUrl, min_size=1, max_size=10)
    return pool


async def closePool() -> None:
    global pool
    if pool is not None:
        await pool.close()
        pool = None


def requirePool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("database pool not opened — call openPool during startup")
    return pool


async def fetchOne(query: str, *args: Any) -> Optional[asyncpg.Record]:
    activePool = requirePool()
    async with activePool.acquire() as connection:
        return await connection.fetchrow(query, *args)


async def fetchAll(query: str, *args: Any) -> list[asyncpg.Record]:
    activePool = requirePool()
    async with activePool.acquire() as connection:
        return await connection.fetch(query, *args)


async def execute(query: str, *args: Any) -> str:
    activePool = requirePool()
    async with activePool.acquire() as connection:
        return await connection.execute(query, *args)
