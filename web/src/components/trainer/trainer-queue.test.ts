import test from "node:test";
import assert from "node:assert/strict";

import { resolveNextPhase } from "@/components/trainer/trainer-queue";

test("resolveNextPhase advances through prompt/attempt/grading", () => {
  assert.equal(resolveNextPhase("prompt", true, false), "user_attempt");
  assert.equal(resolveNextPhase("user_attempt", true, false), "grading");
});

test("resolveNextPhase uses remediation for incorrect answer", () => {
  assert.equal(resolveNextPhase("user_attempt", false, false), "reveal_explanation");
});

test("resolveNextPhase ends in transition after completion", () => {
  assert.equal(resolveNextPhase("grading", true, true), "next_item_transition");
});
