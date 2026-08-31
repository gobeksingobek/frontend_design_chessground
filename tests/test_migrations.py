from __future__ import annotations

from backend.migrations import discover_migrations


def test_migrations_are_ordered_and_cover_canonical_runtime() -> None:
    migrations = discover_migrations()
    assert [migration.version for migration in migrations] == [1, 2]
    assert all(len(migration.checksum) == 64 for migration in migrations)
    sql = "\n".join(migration.path.read_text(encoding="utf-8") for migration in migrations)
    for table in (
        "workspaces", "source_artifacts", "analysis_jobs", "analysis_job_steps",
        "engine_cache", "review_items", "review_propositions", "workspace_state",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql


def test_legacy_bootstrap_schema_is_not_a_runtime_source() -> None:
    paths = {migration.path.name for migration in discover_migrations()}
    assert "schema.sql" not in paths
    assert "analysis_schema.sql" not in paths
