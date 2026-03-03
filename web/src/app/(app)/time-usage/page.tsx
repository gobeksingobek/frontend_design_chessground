import { StatsTable } from "@/components/stats-table";
import { listTimeUsageStats } from "@/lib/api-client";

export default function TimeUsagePage() {
  return (
    <StatsTable
      title="Time usage"
      description="Monthly in-book vs out-of-book time trends."
      queryKey={["time-usage-stats"]}
      queryFn={listTimeUsageStats}
    />
  );
}
