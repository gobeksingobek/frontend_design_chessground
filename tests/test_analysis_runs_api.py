from __future__ import annotations

from backend.api_service import AnalysisRunHistoryEntry, AnalysisRuntimeManager


def test_analysis_runs_schema_and_limit() -> None:
    manager = AnalysisRuntimeManager()
    manager._runs = [
        AnalysisRunHistoryEntry(run_id="r2", run_type="fetch-games", status="failed", started_at="s2", finished_at="f2", error_reason="x"),
        AnalysisRunHistoryEntry(run_id="r1", run_type="full-analysis", status="completed", started_at="s1", finished_at="f1", error_reason=None),
    ]
    result = manager.runs(limit=1)
    assert result.runs[0].run_id == "r2"
    assert result.runs[0].status in {"failed", "completed", "running"}
