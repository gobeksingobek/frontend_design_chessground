import test from "node:test";
import assert from "node:assert/strict";

import { nextEvidenceDrawerState, sortInsightsForDisplay } from "./page-helpers.ts";

test("insights rank by priority then confidence", () => {
  const sorted = sortInsightsForDisplay([
    { title: "B", priority_score: 0.9, confidence: 0.4, source_refs: [] },
    { title: "A", priority_score: 0.9, confidence: 0.8, source_refs: [] },
    { title: "C", priority_score: 0.7, confidence: 0.99, source_refs: [] },
  ]);

  assert.deepEqual(
    sorted.map((row) => row.title),
    ["A", "B", "C"],
  );
});

test("evidence drawer toggles open and close", () => {
  assert.equal(nextEvidenceDrawerState(null, "insight-1"), "insight-1");
  assert.equal(nextEvidenceDrawerState("insight-1", "insight-1"), null);
  assert.equal(nextEvidenceDrawerState("insight-1", "insight-2"), "insight-2");
});
