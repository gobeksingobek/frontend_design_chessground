import test from "node:test";
import assert from "node:assert/strict";

import { toCanonicalTreeSnapshot } from "@/components/tree/tree-explorer-shared";

test("tree canonical schema snapshot values", () => {
  const snapshot = toCanonicalTreeSnapshot(
    { pos_id: 2, repertoire_children: [{}], game_children: [{}, {}] },
    { pos_id: 2, coverage_pct: 50 },
  );

  assert.equal(snapshot.posId, 2);
  assert.equal(snapshot.coveragePct, 50);
  assert.equal(snapshot.repertoireCount, 1);
  assert.equal(snapshot.gameCount, 2);
});
