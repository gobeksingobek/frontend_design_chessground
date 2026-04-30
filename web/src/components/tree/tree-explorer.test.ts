import test from "node:test";
import assert from "node:assert/strict";

import { toCanonicalTreeContract, toCanonicalTreeSnapshot } from "@/components/tree/tree-explorer-shared";

test("tree canonical schema snapshot values", () => {
  const snapshot = toCanonicalTreeSnapshot(
    { pos_id: 2, my_side_only: true, repertoire_children: [{}], game_children: [{}, {}] },
    { pos_id: 2, my_side_only: true, coverage_pct: 50, total_repertoire_moves: 1, covered_by_games: 1, repertoire_children: [{}], game_children: [{}, {}] },
    { pos_id: 2, my_side_only: true, repertoire_children: [{}], game_children: [{}, {}], top_repertoire_branches: [{}], top_game_branches: [{}] },
  );

  assert.equal(snapshot.posId, 2);
  assert.equal(snapshot.coveragePct, 50);
  assert.equal(snapshot.repertoireCount, 1);
  assert.equal(snapshot.gameCount, 2);
});

test("tree canonical schema keeps node identity and coverage across panels", () => {
  const canonical = toCanonicalTreeContract({
    browse: { pos_id: 7, my_side_only: true, repertoire_children: [{ uci_move: "g1f3" } as never, { uci_move: "c2c4" } as never], game_children: [{ uci_move: "g1f3" } as never] },
    coverage: { pos_id: 7, my_side_only: true, repertoire_children: [] as never[], game_children: [] as never[], total_repertoire_moves: 2, covered_by_games: 1, coverage_pct: 50 },
  });
  const snapshot = toCanonicalTreeSnapshot(canonical.browse, canonical.coverage, canonical.metrics);

  assert.equal(canonical.browse.pos_id, canonical.coverage.pos_id);
  assert.equal(canonical.coverage.pos_id, canonical.metrics.pos_id);
  assert.equal(snapshot.posId, 7);
  assert.equal(snapshot.coveragePct, 50);
  assert.equal(snapshot.repertoireCount, 2);
  assert.equal(snapshot.gameCount, 1);
});

test("tree canonical schema falls back to mirrored coverage counts", () => {
  const snapshot = toCanonicalTreeSnapshot(
    null,
    { pos_id: 9, my_side_only: true, coverage_pct: 62.5, repertoire_children: [{}, {}, {}] as never[], game_children: [{}, {}] as never[], total_repertoire_moves: 3, covered_by_games: 2 },
    null,
  );

  assert.equal(snapshot.posId, 9);
  assert.equal(snapshot.coveragePct, 62.5);
  assert.equal(snapshot.repertoireCount, 3);
  assert.equal(snapshot.gameCount, 2);
});
