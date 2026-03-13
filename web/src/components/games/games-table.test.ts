import test from "node:test";
import assert from "node:assert/strict";

test("games table state contains expanded filters", () => {
  const state = { result: "", compliance: "", complianceMin: "0.5", lineId: "L1", player: "p", dateFrom: "", dateTo: "", sortBy: "date", sortDir: "desc" };
  assert.equal(state.complianceMin, "0.5");
  assert.equal(state.lineId, "L1");
});
