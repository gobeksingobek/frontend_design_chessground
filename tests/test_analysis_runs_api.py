from __future__ import annotations

import time

from backend.api_service import AnalysisRunHistoryEntry, AnalysisRuntimeManager
from backend.read_api import normalize_analysis_runs


def test_analysis_runs_sorted_and_limited() -> None:
    manager = AnalysisRuntimeManager()
    manager._runs = [
        AnalysisRunHistoryEntry(run_id="r2", run_type="fetch-games", status="failed", started_at="s2", finished_at="f2", error_reason="x"),
        AnalysisRunHistoryEntry(run_id="r1", run_type="full-analysis", status="completed", started_at="s1", finished_at="f1", error_reason=None),
    ]
    normalized = normalize_analysis_runs(manager.runs(limit=10).runs, limit=1)
    assert normalized[0]["run_id"] == "r2"
    assert normalized[0]["status"] == "failed"


def test_analysis_runtime_status_transitions_completed() -> None:
    manager = AnalysisRuntimeManager()
    job_id = manager.start_job("smoke-test", lambda progress: progress({"message": "done", "done": 1, "total": 1}))

    for _ in range(80):
        if manager.status().state in {"completed", "failed"}:
            break
        time.sleep(0.01)

    runs = manager.runs(limit=5).runs
    assert runs[0].run_id == job_id
    assert runs[0].status == "completed"
    assert runs[0].finished_at is not None
    assert manager.status().state == "completed"


def test_analysis_runtime_status_transitions_failed() -> None:
    manager = AnalysisRuntimeManager()

    def fail_action(_progress):
        raise RuntimeError("boom")

    job_id = manager.start_job("fetch-games", fail_action)
    for _ in range(80):
        if manager.status().state in {"completed", "failed"}:
            break
        time.sleep(0.01)

    runs = manager.runs(limit=5).runs
    assert runs[0].run_id == job_id
    assert runs[0].status == "failed"
    assert runs[0].error_reason == "boom"
    assert manager.status().state == "failed"
