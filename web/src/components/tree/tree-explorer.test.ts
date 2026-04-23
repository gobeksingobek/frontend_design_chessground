import test from "node:test";
import assert from "node:assert/strict";

import { toCanonicalTreeSnapshot } from "@/components/tree/tree-explorer-shared";

test("tree canonical schema snapshot values", () => {
  const snapshot = toCanonicalTreeSnapshot(
    { pos_id: 2, repertoire_children: [{}], game_children: [{}, {}] },
    { pos_id: 2, coverage_pct: 50 },
    { pos_id: 2, repertoire_children: [{}], game_children: [{}, {}] },
  );

  assert.equal(snapshot.posId, 2);
  assert.equal(snapshot.coveragePct, 50);
  assert.equal(snapshot.repertoireCount, 1);
  assert.equal(snapshot.gameCount, 2);
});

test("tree canonical schema keeps endpoint identity and coverage", () => {
  const snapshot = toCanonicalTreeSnapshot(
    null,
    { pos_id: 7, coverage_pct: 37.5 },
    { pos_id: 7, repertoire_children: [{}, {}], game_children: [{}] },
  );

  assert.equal(snapshot.posId, 7);
  assert.equal(snapshot.coveragePct, 37.5);
  assert.equal(snapshot.repertoireCount, 2);
  assert.equal(snapshot.gameCount, 1);
});
