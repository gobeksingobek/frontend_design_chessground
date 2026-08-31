from __future__ import annotations

import argparse
import asyncio

import asyncpg

from backend import db
from backend.migrations import apply_pending_migrations, require_current_schema
from backend.settings import SETTINGS


async def bootstrap_schema(postgres_dsn: str) -> None:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        await apply_pending_migrations(conn)
        await require_current_schema(conn)
        missing = await db.missing_tables(conn, db.REQUIRED_ANALYSIS_TABLES)
        if missing:
            missing_csv = ", ".join(missing)
            raise RuntimeError(f"Bootstrap finished with missing table(s): {missing_csv}")
    finally:
        await conn.close()


async def validate_schema(postgres_dsn: str) -> None:
    conn = await asyncpg.connect(postgres_dsn)
    try:
        await require_current_schema(conn)
        required = db.REQUIRED_ANALYSIS_TABLES + ("sideline_requests",)
        missing = await db.missing_tables(conn, required)
        if missing:
            missing_csv = ", ".join(missing)
            raise RuntimeError(f"Schema validation failed. Missing table(s): {missing_csv}")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply or validate the versioned PostgreSQL runtime schema."
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
