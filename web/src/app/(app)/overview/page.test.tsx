import test from "node:test";
import assert from "node:assert/strict";

import { actionForRunType, canTriggerRunAction, runActionLabel, summarizeRunTimeline } from "./page-helpers.ts";

test("overview timeline action wiring maps run types to retry actions", () => {
  assert.equal(actionForRunType("full-analysis"), "full");
  assert.equal(actionForRunType("engine-only-analysis"), "engine");
  assert.equal(actionForRunType("fetch-games"), "fetch");
  assert.equal(actionForRunType("smoke-test"), "smoke");
});

test("overview run cards produce retry and rerun labels", () => {
  assert.equal(
    runActionLabel({
      run_id: "r1",
      run_type: "fetch-games",
      status: "failed",
      started_at: "2024-01-01T00:00:00Z",
      finished_at: "2024-01-01T00:01:00Z",
      error_reason: "boom",
    }),
    "Retry fetch games",
  );

  assert.equal(
    runActionLabel({
      run_id: "r2",
      run_type: "full-analysis",
      status: "completed",
      started_at: "2024-01-01T00:00:00Z",
      finished_at: "2024-01-01T00:01:00Z",
      error_reason: null,
    }),
    "Run full analysis again",
  );
});

test("overview timeline summary derives current and recent finished runs", () => {
  const summary = summarizeRunTimeline([
    {
      run_id: "r3",
      run_type: "engine-only-analysis",
      status: "running",
      started_at: "2024-01-02T00:00:00Z",
      finished_at: null,
      error_reason: null,
    },
    {
      run_id: "r2",
      run_type: "fetch-games",
      status: "failed",
      started_at: "2024-01-01T01:00:00Z",
      finished_at: "2024-01-01T01:02:00Z",
      error_reason: "boom",
    },
  ]);

  assert.equal(summary.latestRun?.run_id, "r3");
  assert.equal(summary.recentFinishedRun?.run_id, "r2");
});

test("retry interactions disable actions while active run or mutation pending", () => {
  const failedRun = {
    run_id: "r4",
    run_type: "fetch-games",
    status: "failed" as const,
    started_at: "2024-01-03T00:00:00Z",
    finished_at: "2024-01-03T00:01:00Z",
    error_reason: "http 500",
  };
  const runningRun = {
    ...failedRun,
    run_id: "r5",
    status: "running" as const,
    finished_at: null,
    error_reason: null,
  };

  assert.equal(canTriggerRunAction(failedRun, false, false), true);
  assert.equal(canTriggerRunAction(failedRun, true, false), false);
  assert.equal(canTriggerRunAction(failedRun, false, true), false);
  assert.equal(canTriggerRunAction(runningRun, false, false), false);
});
