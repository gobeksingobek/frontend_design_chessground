import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";

interface EvalBarProps {
  evalCp: number | null;
  title?: string;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function evalTone(evalCp: number): string {
  if (evalCp >= 120) return "text-success";
  if (evalCp <= -120) return "text-danger";
  return "text-muted-foreground";
}

export function EvalBar({ evalCp, title = "Evaluation" }: EvalBarProps) {
  if (evalCp === null) {
    return (
      <Card className="gap-2 border-border/80 bg-muted">
        <h4 className="text-sm font-semibold text-foreground">{title}</h4>
        <small className="text-muted-foreground">No centipawn evaluation for this move.</small>
      </Card>
    );
  }

  const normalized = clamp(evalCp, -600, 600);
  const whiteShare = ((normalized + 600) / 1200) * 100;

  return (
    <Card className="gap-3 border-border/80 bg-muted">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-sm font-semibold text-foreground">{title}</h4>
        <span className={cn("text-sm font-semibold", evalTone(evalCp))}>{evalCp > 0 ? `+${evalCp}` : evalCp}</span>
      </div>
      <div className="grid gap-2">
        <div className="flex h-6 w-full overflow-hidden rounded-pill border border-border bg-elevated" role="img" aria-label={`Eval bar, white ${whiteShare.toFixed(1)} percent`}>
          <div className="bg-eval-light transition-[width]" style={{ width: `${whiteShare}%` }} />
          <div className="bg-eval-dark transition-[width]" style={{ width: `${100 - whiteShare}%` }} />
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>White {whiteShare.toFixed(1)}%</span>
          <span>Black {(100 - whiteShare).toFixed(1)}%</span>
        </div>
      </div>
    </Card>
  );
}
