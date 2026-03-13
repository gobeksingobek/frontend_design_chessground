import test from "node:test";
import assert from "node:assert/strict";

import { resolveNextPhase, shouldShowRemediation, shouldShowRetryRequired } from "@/components/trainer/trainer-queue";

test("trainer queue deterministic prompt->attempt->grade->next flow on correct answer", () => {
  const afterPrompt = resolveNextPhase("prompt", "correct");
  const afterAttempt = resolveNextPhase(afterPrompt, "correct");
  const afterGrade = resolveNextPhase(afterAttempt, "correct");

  assert.equal(afterPrompt, "attempt");
  assert.equal(afterAttempt, "grade");
  assert.equal(afterGrade, "next");
});

test("trainer queue deterministic remediation path uses reveal before grade", () => {
  const afterPrompt = resolveNextPhase("prompt", "correct");
  const afterAttempt = resolveNextPhase(afterPrompt, "incorrect");
  const afterReveal = resolveNextPhase(afterAttempt, "correct");

  assert.equal(afterPrompt, "attempt");
  assert.equal(afterAttempt, "reveal");
  assert.equal(afterReveal, "grade");
});

test("grade actions remain deterministic regardless of outcome source", () => {
  assert.equal(resolveNextPhase("grade", "correct"), "next");
  assert.equal(resolveNextPhase("grade", "incorrect"), "next");
});


test("remediation rendering requires incorrect outcome with remediation payload", () => {
  assert.equal(shouldShowRemediation(null), false);
  assert.equal(
    shouldShowRemediation({
      outcome: "correct",
      grade: "good",
      streak_delta: 1,
      item_state: "learned",
      next_item: null,
    }),
    false,
  );
  assert.equal(
    shouldShowRemediation({
      outcome: "incorrect",
      grade: "again",
      streak_delta: -1,
      item_state: "needs_review",
      remediation: {
        best_move_uci: "e2e4",
        principal_variation: ["e2e4", "e7e5"],
        explanation_markdown: "Try the mainline move.",
        retry_required: true,
      },
      next_item: null,
    }),
    true,
  );
});

test("retry-required path only shows CTA when remediation.retry_required is true", () => {
  assert.equal(
    shouldShowRetryRequired({
      outcome: "incorrect",
      grade: "again",
      streak_delta: -1,
      item_state: "needs_review",
      remediation: {
        best_move_uci: "e2e4",
        principal_variation: ["e2e4"],
        explanation_markdown: "Retry.",
        retry_required: false,
      },
      next_item: null,
    }),
    false,
  );
  assert.equal(
    shouldShowRetryRequired({
      outcome: "incorrect",
      grade: "again",
      streak_delta: -1,
      item_state: "needs_review",
      remediation: {
        best_move_uci: "e2e4",
        principal_variation: ["e2e4"],
        explanation_markdown: "Retry.",
        retry_required: true,
      },
      next_item: null,
    }),
    true,
  );
});
