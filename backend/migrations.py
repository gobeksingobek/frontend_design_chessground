from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import asyncpg


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "storage" / "postgres" / "migrations"


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str


def discover_migrations() -> list[Migration]:
    migrations: list[Migration] = []
    for path in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql")):
        version_text, _, name = path.stem.partition("_")
        if not name:
            raise RuntimeError(f"Invalid migration filename: {path.name}")
        sql = path.read_bytes()
        migrations.append(
            Migration(
                version=int(version_text),
                name=name,
                path=path,
                checksum=hashlib.sha256(sql).hexdigest(),
            )
        )
    versions = [migration.version for migration in migrations]
    if len(versions) != len(set(versions)):
        raise RuntimeError("Duplicate PostgreSQL migration version detected.")
    if not migrations:
        raise RuntimeError(f"No PostgreSQL migrations found in {MIGRATIONS_DIR}")
    return migrations


async def _ensure_migration_table(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


async def migration_status(conn: asyncpg.Connection) -> tuple[list[Migration], list[Migration]]:
    await _ensure_migration_table(conn)
    expected = discover_migrations()
    rows = await conn.fetch("SELECT version, name, checksum FROM schema_migrations ORDER BY version")
    applied = {int(row["version"]): row for row in rows}
    for migration in expected:
        row = applied.get(migration.version)
        if row is None:
            continue
        if str(row["name"]) != migration.name or str(row["checksum"]) != migration.checksum:
            raise RuntimeError(
                f"Applied migration {migration.version:04d} does not match {migration.path.name}. "
                "Never edit an applied migration; add a new migration instead."
            )
    unknown = sorted(set(applied) - {migration.version for migration in expected})
    if unknown:
        raise RuntimeError(f"Database contains unknown migration versions: {unknown}")
    pending = [migration for migration in expected if migration.version not in applied]
    return expected, pending


async def apply_pending_migrations(conn: asyncpg.Connection) -> list[Migration]:
    _, pending = await migration_status(conn)
    for migration in pending:
        sql = migration.path.read_text(encoding="utf-8")
        async with conn.transaction():
            await conn.execute(sql)
            await conn.execute(
                "INSERT INTO schema_migrations(version, name, checksum) VALUES($1, $2, $3)",
                migration.version,
                migration.name,
                migration.checksum,
            )
    return pending


async def require_current_schema(conn: asyncpg.Connection) -> None:
    _, pending = await migration_status(conn)
    if pending:
        names = ", ".join(migration.path.name for migration in pending)
        raise RuntimeError(
            f"PostgreSQL schema is behind. Pending migration(s): {names}. "
            "Run `python -m backend.bootstrap_postgres_schema` before starting services."
        )
