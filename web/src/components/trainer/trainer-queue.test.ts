import test from "node:test";
import assert from "node:assert/strict";

import { resolveNextPhase } from "@/components/trainer/trainer-queue";

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
