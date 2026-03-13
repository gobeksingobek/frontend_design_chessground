import test from "node:test";
import assert from "node:assert/strict";

import { buildQueueStatusMap, deriveSelectedIdAfterAction, summarizeReviewActionResult } from "@/components/review/review-actions-panel";
import type { ReviewActionResponse } from "@/lib/types";

function sampleResult(overrides: Partial<ReviewActionResponse> = {}): ReviewActionResponse {
  return {
    success: true,
    message: "ok",
    proposition: {
      id: 12,
      proposition_type: "MISSING_COVERAGE_BRANCH",
      proposition_key: "k",
      status: "APPROVED",
      evidence_count: 8,
      threshold_count: 5,
      dismissed_count: null,
      pos_id: 22,
      uci_move: "d2d4",
      line_id_hint: "line-1",
      detail: { reason: "coverage" },
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:01:00Z",
      decided_at: "2024-01-01T00:01:00Z",
    },
    status_change: { before: "PENDING", after: "APPROVED" },
    queue_change: { before: null, after: { proposition_id: 12, queue_status: "QUEUED", queued_at: "now", proposition_status: "APPROVED", evidence_count: 8, threshold_count: 5, pos_id: 22, uci_move: "d2d4", line_id_hint: "line-1", updated_at: "now" } },
    queue_delta: { proposition_id: 12, before_queue_status: null, after_queue_status: "QUEUED", added_to_queue: true, removed_from_queue: false },
    priority_change: { line_id: "line-1", before: 0, after: 1 },
    ...overrides,
  };
}

test("summarizeReviewActionResult includes status, queue, and priority deltas", () => {
  const summary = summarizeReviewActionResult(sampleResult());
  assert.match(summary, /Status PENDING→APPROVED/);
  assert.match(summary, /queue none→QUEUED/);
  assert.match(summary, /priority 0→1/);
});

test("buildQueueStatusMap creates lookup by proposition id", () => {
  const map = buildQueueStatusMap([
    { proposition_id: 1, queue_status: "QUEUED" },
    { proposition_id: 2, queue_status: "PROCESSING" },
  ]);
  assert.equal(map.get(1), "QUEUED");
  assert.equal(map.get(2), "PROCESSING");
});

test("deriveSelectedIdAfterAction prefers action proposition id", () => {
  const next = deriveSelectedIdAfterAction(3, sampleResult());
  assert.equal(next, 12);

  const unchanged = deriveSelectedIdAfterAction(3, sampleResult({ proposition: null }));
  assert.equal(unchanged, 3);
});


test("summarizeReviewActionResult renders queue delta segment", () => {
  const summary = summarizeReviewActionResult(sampleResult());
  assert.match(summary, /queue Δ none→QUEUED/);
});

test("inspect to apply loop updates selected proposition and queue map", () => {
  const selectedAfterInspect = 101;
  const selectedAfterApply = deriveSelectedIdAfterAction(
    selectedAfterInspect,
    sampleResult({ proposition: { ...sampleResult().proposition!, id: selectedAfterInspect } }),
  );
  assert.equal(selectedAfterApply, 101);

  const queued = buildQueueStatusMap([{ proposition_id: 101, queue_status: "QUEUED" }]);
  assert.equal(queued.get(101), "QUEUED");
});
