import test from "node:test";
import assert from "node:assert/strict";

import { refreshReviewPageStateAtomically } from "@/app/(app)/review/review-page-state";

test("refreshReviewPageStateAtomically invalidates review items, actions, and queue", async () => {
  const calls: string[] = [];
  const queryClient = {
    invalidateQueries: async ({ queryKey }: { queryKey: string[] }) => {
      calls.push(queryKey.join("/"));
    },
  };

  await refreshReviewPageStateAtomically(queryClient as never);

  assert.deepEqual(calls.sort(), ["review-actions", "review-branch-queue", "review-items"]);
});
