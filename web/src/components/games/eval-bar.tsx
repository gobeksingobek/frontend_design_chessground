import { Card } from "@/components/ui/card";

interface EvalBarProps {
  evalCp: number | null;
  title?: string;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function EvalBar({ evalCp, title = "Evaluation" }: EvalBarProps) {
  if (evalCp === null) {
    return (
      <Card className="gap-2 bg-panel-muted">
        <h4 className="text-sm font-semibold">{title}</h4>
        <small className="text-text-muted">No centipawn evaluation for this move.</small>
      </Card>
    );
  }

  const normalized = clamp(evalCp, -600, 600);
  const whiteShare = ((normalized + 600) / 1200) * 100;

  return (
    <Card className="gap-2 bg-panel-muted">
      <h4 className="text-sm font-semibold">{title}</h4>
      <div className="flex h-5 w-full overflow-hidden rounded-pill border border-border" role="img" aria-label={`Eval bar, white ${whiteShare.toFixed(1)} percent`}>
        <div className="bg-slate-50" style={{ width: `${whiteShare}%` }} />
        <div className="bg-slate-950" style={{ width: `${100 - whiteShare}%` }} />
      </div>
      <small className="text-text-muted">CP: {evalCp > 0 ? `+${evalCp}` : evalCp}</small>
    </Card>
  );
}
