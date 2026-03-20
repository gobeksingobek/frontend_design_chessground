import { Badge } from "@/components/ui/badge";

const toneMap = {
  best: "accent",
  excellent: "success",
  good: "success",
  inaccuracy: "warning",
  mistake: "danger",
  blunder: "danger",
  book: "neutral",
} as const;

const classNameMap = {
  best: "border-primary/35 bg-primary/15 text-primary",
  excellent: "border-success/35 bg-success/15 text-success",
  good: "border-success/20 bg-success/10 text-success",
  inaccuracy: "border-warning/35 bg-warning/15 text-warning",
  mistake: "border-danger/30 bg-danger/12 text-danger",
  blunder: "border-danger/45 bg-danger/20 text-danger",
  book: "border-secondary/30 bg-secondary/15 text-secondary",
  neutral: "",
} as const;

export function MoveQualityBadge({ label }: { label: string | null }) {
  const normalized = label?.toLowerCase() ?? "neutral";
  const tone = toneMap[normalized as keyof typeof toneMap] ?? "neutral";
  const className = classNameMap[normalized as keyof typeof classNameMap] ?? classNameMap.neutral;

  return <Badge tone={tone} className={className}>{label ?? "-"}</Badge>;
}
