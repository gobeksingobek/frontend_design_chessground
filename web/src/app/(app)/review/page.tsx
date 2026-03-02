import { StatsTable } from "@/components/stats-table";
import { listReviewItems } from "@/lib/api-client";

export default function ReviewPage() {
  return (
    <StatsTable
      title="Review"
      description="Review items generated from your deviations and coverage gaps."
      queryKey={["review-items"]}
      queryFn={listReviewItems}
    />
  );
}
