import test from "node:test";
import assert from "node:assert/strict";

import { applyCursorKey } from "@/components/games/game-detail";

test("applyCursorKey moves cursor next and prev", () => {
  assert.equal(applyCursorKey("ArrowRight", 0, 4), 1);
  assert.equal(applyCursorKey("ArrowLeft", 1, 4), 0);
});

test("applyCursorKey jumps to start and end", () => {
  assert.equal(applyCursorKey("ArrowUp", 1, 4), 4);
  assert.equal(applyCursorKey("ArrowDown", 3, 4), 0);
});
