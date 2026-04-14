import test from "node:test";
import assert from "node:assert/strict";

import { applyCursorKey, buildGameRouteQuery, isCursorNavigationKey } from "@/components/games/game-detail";

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

test("applyCursorKey handles boundary start/end jumps from arrows", () => {
  assert.equal(applyCursorKey("ArrowUp", 0, 8), 8);
  assert.equal(applyCursorKey("ArrowDown", 8, 8), 0);
});

test("applyCursorKey respects bounds", () => {
  assert.equal(applyCursorKey("ArrowLeft", 0, 4), 0);
  assert.equal(applyCursorKey("ArrowRight", 4, 4), 4);
});

test("applyCursorKey ignores unsupported keys", () => {
  assert.equal(applyCursorKey("Enter", 2, 4), 2);
});

test("isCursorNavigationKey marks keys that should retain focus", () => {
  assert.equal(isCursorNavigationKey("Home"), true);
  assert.equal(isCursorNavigationKey("End"), true);
  assert.equal(isCursorNavigationKey("ArrowLeft"), true);
  assert.equal(isCursorNavigationKey("ArrowRight"), true);
  assert.equal(isCursorNavigationKey("Enter"), false);
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
