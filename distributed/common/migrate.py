from __future__ import annotations

import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger("distributed.migrate")

migrationsDir = Path(__file__).resolve().parent.parent / "deployment" / "migrations"

MIGRATION_LOCK_KEY = 875533201


async def ensureSchema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as connection:
        await connection.execute("select pg_advisory_lock($1)", MIGRATION_LOCK_KEY)
        try:
            await connection.execute(
                "create table if not exists schema_migrations (filename text primary key, applied_at timestamptz not null default now())"
            )
            appliedRows = await connection.fetch("select filename from schema_migrations")
            applied = {row["filename"] for row in appliedRows}
            for migrationFile in sorted(migrationsDir.glob("*.sql")):
                if migrationFile.name in applied:
                    continue
                logger.info("applying migration %s", migrationFile.name)
                sql = migrationFile.read_text()
                async with connection.transaction():
                    await connection.execute(sql)
                    await connection.execute(
                        "insert into schema_migrations (filename) values ($1)", migrationFile.name
                    )
        finally:
            await connection.execute("select pg_advisory_unlock($1)", MIGRATION_LOCK_KEY)
