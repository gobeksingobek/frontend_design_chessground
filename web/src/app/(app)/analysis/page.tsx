import { SidelineAnalysisForm } from "@/components/analysis/sideline-analysis-form";
import { ChessBoard } from "@/components/chess/chess-board";

function firstParam(value: string | string[] | undefined): string {
  if (!value) return "";
  if (Array.isArray(value)) return value[0] ?? "";
  return value;
}

export default function AnalysisPage({
  searchParams,
}: {
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const initialGameId = firstParam(searchParams.game_id);
  const movePlyRaw = firstParam(searchParams.move_ply);
  const initialMovePly = movePlyRaw ? Number(movePlyRaw) : null;
  const initialFen = firstParam(searchParams.fen);
  const initialBranchMoves = firstParam(searchParams.branch_moves);

  return (
    <div className="stack">
      <h2>Analysis Board</h2>
      <p>Run a quick local WASM eval for your first custom move, then queue authoritative sideline analysis.</p>
      <div className="board-page-layout">
        <div className="card">
          <ChessBoard fen={initialFen} title="Live position" size="large" />
        </div>
        <div className="card menu-card">
          <SidelineAnalysisForm
            title="Create sideline from custom position"
            initialGameId={initialGameId}
            initialMovePly={Number.isFinite(initialMovePly) ? initialMovePly : null}
            initialFen={initialFen}
            initialBranchMoves={initialBranchMoves}
          />
        </div>
      </div>
    </div>
  );
}
