import { PageContainer, PageSection } from "@/components/app-shell";
import { SidelineAnalysisForm } from "@/components/analysis/sideline-analysis-form";
import { ChessBoard } from "@/components/chess/chess-board";
import { DetailPane, HeroWorkspaceSection } from "@/components/ui/page-patterns";
import { CaptionText, CardTitle, MutedText } from "@/components/ui/typography";

function firstParam(value: string | string[] | undefined): string {
  if (!value) return "";
  if (Array.isArray(value)) return value[0] ?? "";
  return value;
}

export default function AnalysisPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined>; }) {
  const initialGameId = firstParam(searchParams.game_id);
  const movePlyRaw = firstParam(searchParams.move_ply);
  const initialMovePly = movePlyRaw ? Number(movePlyRaw) : null;
  const initialFen = firstParam(searchParams.fen);
  const initialBranchMoves = firstParam(searchParams.branch_moves);
  const resolvedMovePly = Number.isFinite(initialMovePly) ? initialMovePly : null;

  return (
    <PageContainer title="Board Analysis" description="Run a quick local WASM eval, inspect the current position, and queue authoritative sideline analysis.">
      <PageSection>
        <HeroWorkspaceSection
          title="Analysis Board"
          description="Run a quick local WASM eval for your first custom move, then queue authoritative sideline analysis."
          hero={(
            <ChessBoard
              fen={initialFen}
              title="Live position"
              subtitle="Explore a position with the same presentation used in game review and training workflows."
              size="large"
              surface="plain"
              className="h-full max-w-none"
            />
          )}
          heroClassName="gap-5"
          support={(
            <DetailPane
              title="Create sideline from custom position"
              description="Queue the same sideline workflow from the utility rail so the board remains the dominant surface."
              className="bg-elevated"
            >
              <SidelineAnalysisForm
                title="Create sideline from custom position"
                initialGameId={initialGameId}
                initialMovePly={resolvedMovePly}
                initialFen={initialFen}
                initialBranchMoves={initialBranchMoves}
              />
            </DetailPane>
          )}
        >
          <DetailPane
            title="Position context"
            description="Initial route state still comes from the existing query params so deep links from game review and other tools keep working."
          >
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
                <CaptionText>Game id</CaptionText>
                <CardTitle className="mt-2 text-base">{initialGameId || "Not provided"}</CardTitle>
                <MutedText className="mt-2">Links the queued sideline back to the originating game when available.</MutedText>
              </div>
              <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
                <CaptionText>Move ply</CaptionText>
                <CardTitle className="mt-2 text-base">{resolvedMovePly ?? "Not provided"}</CardTitle>
                <MutedText className="mt-2">Keeps move-level context aligned with the source position used to seed analysis.</MutedText>
              </div>
              <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
                <CaptionText>Starting FEN</CaptionText>
                <CardTitle className="mt-2 break-all text-base">{initialFen || "Default starting position"}</CardTitle>
                <MutedText className="mt-2">The board opens from this exact position when a FEN is supplied.</MutedText>
              </div>
              <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
                <CaptionText>Branch moves</CaptionText>
                <CardTitle className="mt-2 break-all text-base">{initialBranchMoves || "Not provided"}</CardTitle>
                <MutedText className="mt-2">Candidate UCI moves continue to prefill the sideline queue form for quick iteration.</MutedText>
              </div>
            </div>
          </DetailPane>
        </HeroWorkspaceSection>
      </PageSection>
    </PageContainer>
  );
}
