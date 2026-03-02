from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import asyncpg

from backend import db
from backend.settings import SETTINGS


def _analysis_schema_sql_path() -> Path:
    return Path(__file__).resolve().parents[1] / "storage" / "postgres" / "analysis_schema.sql"


async def bootstrap_schema(postgres_dsn: str) -> None:
    sql_path = _analysis_schema_sql_path()
    if not sql_path.exists():
        raise RuntimeError(f"Schema file not found: {sql_path}")

    sql_text = sql_path.read_text(encoding="utf-8")
    conn = await asyncpg.connect(postgres_dsn)
    try:
        await conn.execute(sql_text)
        await conn.execute(db.CREATE_TABLE_SQL)
        missing = await db.missing_tables(conn, db.REQUIRED_ANALYSIS_TABLES)
        if missing:
            missing_csv = ", ".join(missing)
            raise RuntimeError(f"Bootstrap finished with missing table(s): {missing_csv}")
    finally:
        await conn.close()


async def validate_schema(postgres_dsn: str) -> None:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        required = db.REQUIRED_ANALYSIS_TABLES + ("sideline_requests",)
        missing = await db.missing_tables(conn, required)
        if missing:
            missing_csv = ", ".join(missing)
            raise RuntimeError(f"Schema validation failed. Missing table(s): {missing_csv}")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create/validate PostgreSQL schema for API + web reads."
    )
    parser.add_argument(
        "--dsn",
        default=SETTINGS.postgres_dsn,
        help="Postgres DSN (defaults to POSTGRES_DSN env).",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate required tables; do not apply schema SQL.",
    )
    args = parser.parse_args()

    if args.validate_only:
        asyncio.run(validate_schema(args.dsn))
        print("Schema validation successful.")
        return

    asyncio.run(bootstrap_schema(args.dsn))
    print("Schema bootstrap successful.")


if __name__ == "__main__":
    main()
