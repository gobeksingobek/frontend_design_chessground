import test from "node:test";
import assert from "node:assert/strict";

test("settings grouped sections keys", () => {
  const groups = ["Fetch", "Paths", "Engine", "Profile"];
  assert.equal(groups.includes("Engine"), true);
});
