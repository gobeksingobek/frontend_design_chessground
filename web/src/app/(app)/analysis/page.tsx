import { PageContainer, PageSection } from "@/components/app-shell";
import { SidelineAnalysisForm } from "@/components/analysis/sideline-analysis-form";
import { BoardWorkspace } from "@/components/chess/board-workspace";
import { ChessBoard } from "@/components/chess/chess-board";
import { SectionHeader } from "@/components/ui/section-header";

function firstParam(value: string | string[] | undefined): string { if (!value) return ""; if (Array.isArray(value)) return value[0] ?? ""; return value; }

export default function AnalysisPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined>; }) {
  const initialGameId = firstParam(searchParams.game_id);
  const movePlyRaw = firstParam(searchParams.move_ply);
  const initialMovePly = movePlyRaw ? Number(movePlyRaw) : null;
  const initialFen = firstParam(searchParams.fen);
  const initialBranchMoves = firstParam(searchParams.branch_moves);

  return (
    <PageContainer title="Board Analysis" description="Run a quick local WASM eval, inspect the current position, and queue authoritative sideline analysis.">
      <PageSection>
        <SectionHeader title="Analysis Board" description="Run a quick local WASM eval for your first custom move, then queue authoritative sideline analysis." />
        <BoardWorkspace
          board={<ChessBoard fen={initialFen} title="Live position" subtitle="Explore a position with the same presentation used in game review and training workflows." size="large" surface="plain" className="h-full max-w-none" />}
          aside={<SidelineAnalysisForm title="Create sideline from custom position" initialGameId={initialGameId} initialMovePly={Number.isFinite(initialMovePly) ? initialMovePly : null} initialFen={initialFen} initialBranchMoves={initialBranchMoves} />}
        />
      </PageSection>
    </PageContainer>
  );
}
