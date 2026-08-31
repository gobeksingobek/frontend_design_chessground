import test from "node:test";
import assert from "node:assert/strict";

import { resolveFocusWrapTarget } from "@/components/ui/responsive-context-panel";

test("context panel wraps reverse tabbing from the first control", () => {
  assert.equal(resolveFocusWrapTarget(true, true, false), "last");
});

test("context panel wraps forward tabbing from the last control", () => {
  assert.equal(resolveFocusWrapTarget(false, false, true), "first");
});

test("context panel leaves focus alone inside the control sequence", () => {
  assert.equal(resolveFocusWrapTarget(false, false, false), null);
});
