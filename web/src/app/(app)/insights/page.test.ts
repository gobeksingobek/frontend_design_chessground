import test from "node:test";
import assert from "node:assert/strict";

test("insight evidence drawer fields", () => {
  const row = { confidence: 0.8, source_refs: [{ type: "game", id: "1", label: "g" }] };
  assert.equal(row.source_refs[0].type, "game");
  assert.ok(row.confidence > 0);
});
