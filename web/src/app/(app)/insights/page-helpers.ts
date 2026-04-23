import type { InsightRow } from "@/lib/types";

export function sortInsightsForDisplay(rows: InsightRow[]): InsightRow[] {
  return [...rows].sort((left, right) => {
    const byPriority = (right.priority_score ?? 0) - (left.priority_score ?? 0);
    if (byPriority !== 0) return byPriority;
    const byConfidence = (right.confidence ?? 0) - (left.confidence ?? 0);
    if (byConfidence !== 0) return byConfidence;
    return String(left.title ?? "").localeCompare(String(right.title ?? ""));
  });
}

export function nextEvidenceDrawerState(currentOpenInsightId: string | null, insightId: string): string | null {
  return currentOpenInsightId === insightId ? null : insightId;
}

export function insightId(row: InsightRow, index: number): string {
  return `${String(row.title ?? "untitled")}-${index}`;
}
