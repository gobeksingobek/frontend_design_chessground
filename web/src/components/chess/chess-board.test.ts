import test from "node:test";
import assert from "node:assert/strict";

import { buildMoveAttempt } from "@/components/chess/chess-board";

test("buildMoveAttempt creates a UCI move payload", () => {
  assert.deepEqual(buildMoveAttempt("e2", "e4"), {
    uci: "e2e4",
    from: "e2",
    to: "e4",
  });
});
