import test from "node:test";
import assert from "node:assert/strict";

import { mapBackendFieldErrors, SECTIONS } from "./page.tsx";

test("settings page defines grouped section order", () => {
  assert.deepEqual(
    SECTIONS.map((section) => section.title),
    ["Paths", "Engine", "Profile", "Fetch"],
  );
});

test("maps backend runtime validation errors to form fields", () => {
  const mapped = mapBackendFieldErrors(
    JSON.stringify({
      detail: [
        { field: "days_back", code: "range", message: "Must be between 1 and 3650" },
        { field: "engine_depth", code: "type", message: "Expected integer" },
      ],
    }),
  );

  assert.equal(mapped.daysBack, "Must be between 1 and 3650");
  assert.equal(mapped.engineDepth, "Expected integer");
});
