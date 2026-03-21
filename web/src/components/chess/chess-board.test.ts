import test from "node:test";
import assert from "node:assert/strict";

import { buildMoveAttempt, isKingInCheck } from "@/components/chess/chess-board";

test("buildMoveAttempt creates a UCI move payload", () => {
  assert.deepEqual(buildMoveAttempt("e2", "e4"), {
    uci: "e2e4",
    from: "e2",
    to: "e4",
  });
});

test("isKingInCheck returns the checked king square for side to move", () => {
  assert.equal(isKingInCheck("4k3/8/8/8/4R3/8/8/4K3 b - - 0 1"), "e8");
});

test("isKingInCheck returns null when side to move is not in check", () => {
  assert.equal(isKingInCheck("4k3/8/8/8/8/8/3r4/4K3 w - - 0 1"), null);
});
