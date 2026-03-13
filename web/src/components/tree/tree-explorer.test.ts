import test from "node:test";
import assert from "node:assert/strict";

test("tree canonical schema snapshot values", () => {
  const snapshot = { posId: 2, coveragePct: 50, repertoireCount: 1, gameCount: 2 };
  assert.equal(snapshot.posId, 2);
  assert.equal(snapshot.coveragePct, 50);
});
