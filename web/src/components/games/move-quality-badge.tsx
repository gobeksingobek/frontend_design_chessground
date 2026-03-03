interface MoveQualityBadgeProps {
  label: string | null;
}

function qualityTone(label: string | null): string {
  const normalized = label?.trim().toLowerCase();
  if (!normalized) return "neutral";
  if (["best", "excellent", "good", "book"].includes(normalized)) return "good";
  if (["inaccuracy", "dubious"].includes(normalized)) return "warn";
  if (["mistake", "blunder"].includes(normalized)) return "bad";
  return "neutral";
}

export function MoveQualityBadge({ label }: MoveQualityBadgeProps) {
  const tone = qualityTone(label);
  return <span className={`quality-badge ${tone}`}>{label ?? "-"}</span>;
}
