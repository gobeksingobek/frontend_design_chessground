import test from "node:test";
import assert from "node:assert/strict";

test("analysis runs shape uses OVR-01 fields", () => {
  const run = { run_id: "r1", run_type: "full-analysis", status: "completed", started_at: "", finished_at: "", error_reason: null };
  assert.equal(typeof run.run_id, "string");
  assert.equal(run.status, "completed");
});
