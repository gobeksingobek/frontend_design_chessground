import test from "node:test";
import assert from "node:assert/strict";

import { actionForRunType, runActionLabel } from "./page-helpers";

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
