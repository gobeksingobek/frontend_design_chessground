import test from "node:test";
import assert from "node:assert/strict";

import { applyStoredGamesTableState, buildGamesQueryKey, DEFAULT_GAMES_TABLE_STATE } from "@/components/games/games-table";

test("applyStoredGamesTableState merges defaults", () => {
  const state = applyStoredGamesTableState({ player: "alpha", sortDir: "asc" });
  assert.equal(state.player, "alpha");
  assert.equal(state.sortDir, "asc");
  assert.equal(state.sortBy, DEFAULT_GAMES_TABLE_STATE.sortBy);
});

test("buildGamesQueryKey is stable and ordered", () => {
  const key = buildGamesQueryKey({
    ...DEFAULT_GAMES_TABLE_STATE,
    player: "beta",
    sortBy: "compliance",
  });
  assert.deepEqual(key.slice(0, 3), ["games", "", ""]);
  assert.equal(key.at(-2), "compliance");
  assert.equal(key.at(-1), "desc");
});
