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
      <div className="eval-bar-panel">
        <h4>{title}</h4>
        <small>No centipawn evaluation for this move.</small>
      </div>
    );
  }

  const normalized = clamp(evalCp, -600, 600);
  const whiteShare = ((normalized + 600) / 1200) * 100;

  return (
    <div className="eval-bar-panel">
      <h4>{title}</h4>
      <div className="eval-bar" role="img" aria-label={`Eval bar, white ${whiteShare.toFixed(1)} percent`}>
        <div className="eval-bar-white" style={{ width: `${whiteShare}%` }} />
        <div className="eval-bar-black" style={{ width: `${100 - whiteShare}%` }} />
      </div>
      <small>CP: {evalCp > 0 ? `+${evalCp}` : evalCp}</small>
    </div>
  );
}
