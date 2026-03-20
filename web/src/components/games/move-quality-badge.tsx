import { Badge } from "@/components/ui/badge";

const toneMap = {
  best: "success",
  excellent: "success",
  good: "success",
  inaccuracy: "warning",
  mistake: "danger",
  blunder: "danger",
  book: "accent",
} as const;

export function MoveQualityBadge({ label }: { label: string | null }) {
  const normalized = label?.toLowerCase() ?? "neutral";
  const tone = toneMap[normalized as keyof typeof toneMap] ?? "neutral";

  return <Badge tone={tone}>{label ?? "-"}</Badge>;
}
