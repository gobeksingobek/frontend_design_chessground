import test from "node:test";
import assert from "node:assert/strict";
import { applyStoredGamesTableState, buildGamesQueryKey, DEFAULT_GAMES_TABLE_STATE } from "./games-table.tsx";
import { buildGamesPageQueryParams, parseGamesPageState } from "../../app/(app)/games/page-state.ts";

test("games table query key includes full filter and sorting controls", () => {
  const state = {
    ...DEFAULT_GAMES_TABLE_STATE,
    result: "1-0",
    complianceMin: "0.75",
    lineId: "line-a",
    player: "Alpha",
    dateFrom: "2024-01-01",
    dateTo: "2024-01-31",
    sortBy: "result" as const,
    sortDir: "asc" as const,
  };
  const key = buildGamesQueryKey(state);
  assert.equal(key[0], "games");
  assert.equal(key.includes("1-0"), true);
  assert.equal(key.includes("line-a"), true);
  assert.equal(key.at(-1), "asc");
});

test("games page state persists and restores via query params", () => {
  const state = {
    ...DEFAULT_GAMES_TABLE_STATE,
    complianceMin: "0.5",
    lineId: "L1",
    player: "Alpha",
    dateFrom: "2024-01-01",
    dateTo: "2024-01-05",
    sortBy: "compliance" as const,
    sortDir: "asc" as const,
  };

  const params = buildGamesPageQueryParams(state);
  const restored = parseGamesPageState(params);

  assert.equal(restored.complianceMin, "0.5");
  assert.equal(restored.lineId, "L1");
  assert.equal(restored.player, "Alpha");
  assert.equal(restored.sortBy, "compliance");
  assert.equal(restored.sortDir, "asc");
});

test("invalid persisted sort settings fall back to deterministic defaults", () => {
  const restored = applyStoredGamesTableState({ sortBy: "invalid" as never, sortDir: "down" as never });
  assert.equal(restored.sortBy, "date");
  assert.equal(restored.sortDir, "desc");
});
