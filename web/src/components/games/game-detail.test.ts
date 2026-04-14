import test from "node:test";
import assert from "node:assert/strict";

import { applyCursorKey, buildGameRouteQuery } from "@/components/games/game-detail";

test("applyCursorKey moves cursor next and prev", () => {
  assert.equal(applyCursorKey("ArrowRight", 0, 4), 1);
  assert.equal(applyCursorKey("ArrowLeft", 1, 4), 0);
});

test("applyCursorKey jumps to start and end with arrows", () => {
  assert.equal(applyCursorKey("ArrowUp", 1, 4), 4);
  assert.equal(applyCursorKey("ArrowDown", 3, 4), 0);
});

test("applyCursorKey jumps to start and end with Home/End", () => {
  assert.equal(applyCursorKey("End", 1, 4), 4);
  assert.equal(applyCursorKey("Home", 3, 4), 0);
});

test("applyCursorKey respects bounds", () => {
  assert.equal(applyCursorKey("ArrowLeft", 0, 4), 0);
  assert.equal(applyCursorKey("ArrowRight", 4, 4), 4);
});

test("applyCursorKey ignores unsupported keys", () => {
  assert.equal(applyCursorKey("Enter", 2, 4), 2);
});

test("buildGameRouteQuery preserves tab and orientation with ply", () => {
  assert.deepEqual(buildGameRouteQuery(12, "moves", "black"), {
    ply: "12",
    tab: "moves",
    orientation: "black",
  });
});

test("buildGameRouteQuery omits ply when on initial position", () => {
  assert.deepEqual(buildGameRouteQuery(null, "board", "white"), {
    tab: "board",
    orientation: "white",
  });
});
