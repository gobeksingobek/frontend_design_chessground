import type { QueryClient } from "@tanstack/react-query";

export async function refreshReviewPageStateAtomically(queryClient: QueryClient): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["review-items"] }),
    queryClient.invalidateQueries({ queryKey: ["review-actions"] }),
    queryClient.invalidateQueries({ queryKey: ["review-branch-queue"] }),
  ]);
}
