"use client";

import { useQueryClient } from "@tanstack/react-query";

import { ReviewActionsPanel } from "@/components/review/review-actions-panel";
import { StatsTable } from "@/components/stats-table";
import { listReviewItems } from "@/lib/api-client";

import { refreshReviewPageStateAtomically } from "./review-page-state";

export default function ReviewPage() {
  const queryClient = useQueryClient();

  return (
    <div className="stack">
      <StatsTable
        title="Review"
        description="Review items generated from your deviations and coverage gaps."
        queryKey={["review-items"]}
        queryFn={listReviewItems}
      />
      <ReviewActionsPanel onActionCommitted={() => refreshReviewPageStateAtomically(queryClient)} />
    </div>
  );
}
