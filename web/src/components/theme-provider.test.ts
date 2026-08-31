import test from "node:test";
import assert from "node:assert/strict";

import { resolveStoredTheme } from "@/components/theme-provider";

test("theme defaults to the dark ChessGround workspace", () => {
  assert.equal(resolveStoredTheme(null), "dark");
  assert.equal(resolveStoredTheme("system"), "dark");
});

test("theme preserves explicit light and dark choices", () => {
  assert.equal(resolveStoredTheme("light"), "light");
  assert.equal(resolveStoredTheme("dark"), "dark");
});
