import { SidelineAnalysisForm } from "@/components/analysis/sideline-analysis-form";
import { ChessBoard } from "@/components/chess/chess-board";
import { Card } from "@/components/ui/card";
import { SectionHeader } from "@/components/ui/section-header";

function firstParam(value: string | string[] | undefined): string { if (!value) return ""; if (Array.isArray(value)) return value[0] ?? ""; return value; }

export default function AnalysisPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined>; }) {
  const initialGameId = firstParam(searchParams.game_id);
  const movePlyRaw = firstParam(searchParams.move_ply);
  const initialMovePly = movePlyRaw ? Number(movePlyRaw) : null;
  const initialFen = firstParam(searchParams.fen);
  const initialBranchMoves = firstParam(searchParams.branch_moves);

  return (
    <div className="grid gap-4">
      <SectionHeader title="Analysis Board" description="Run a quick local WASM eval for your first custom move, then queue authoritative sideline analysis." />
      <div className="grid gap-4 xl:grid-cols-board">
        <Card><ChessBoard fen={initialFen} title="Live position" size="large" /></Card>
        <Card className="xl:sticky xl:top-4 xl:self-start"><SidelineAnalysisForm title="Create sideline from custom position" initialGameId={initialGameId} initialMovePly={Number.isFinite(initialMovePly) ? initialMovePly : null} initialFen={initialFen} initialBranchMoves={initialBranchMoves} /></Card>
      </div>
    </div>
  );
}
