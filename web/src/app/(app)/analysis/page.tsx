import { PageContainer, PageSection } from "@/components/app-shell";
import { SidelineAnalysisForm } from "@/components/analysis/sideline-analysis-form";
import { ChessBoard } from "@/components/chess/chess-board";
import { BoardWorkspace } from "@/components/chess/board-workspace";
import { DetailPane, UtilityPanel, UtilityPanelGroup, UtilityPanelStack } from "@/components/ui/page-patterns";
import { CaptionText, CardTitle, MutedText } from "@/components/ui/typography";

function firstParam(value: string | string[] | undefined): string {
  if (!value) return "";
  if (Array.isArray(value)) return value[0] ?? "";
  return value;
}

function ContextValueCard({
  label,
  value,
  description,
  breakValue,
}: {
  label: string;
  value: string | number;
  description: string;
  breakValue?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
      <CaptionText>{label}</CaptionText>
      <CardTitle className={breakValue ? "mt-2 break-all text-base" : "mt-2 text-base"}>{value}</CardTitle>
      <MutedText className="mt-2">{description}</MutedText>
    </div>
  );
}

export default async function AnalysisPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>>; }) {
  const query = await searchParams;
  const initialGameId = firstParam(query.game_id);
  const movePlyRaw = firstParam(query.move_ply);
  const initialMovePly = movePlyRaw ? Number(movePlyRaw) : null;
  const initialFen = firstParam(query.fen);
  const initialBranchMoves = firstParam(query.branch_moves);
  const resolvedMovePly = Number.isFinite(initialMovePly) ? initialMovePly : null;

  return (
    <PageContainer title="Board Analysis" description="Run a quick local WASM eval, inspect the current position, and queue authoritative sideline analysis.">
      <PageSection>
        <BoardWorkspace
          header={(
            <div className="grid gap-2">
              <div className="grid gap-1">
                <h2 className="text-xl font-semibold tracking-tight text-foreground">Analysis board</h2>
                <MutedText>
                  Run a quick local WASM eval for your first custom move, then queue authoritative sideline analysis without pushing the board out of focus.
                </MutedText>
              </div>
            </div>
          )}
          board={(
            <ChessBoard
              fen={initialFen}
              title="Live position"
              subtitle="Explore a position with the same presentation used in game review and training workflows."
              size="large"
              surface="plain"
              className="h-full max-w-none"
            />
          )}
          main={(
            <DetailPane
              title="Position context"
              description="Initial route state still comes from the existing query params so deep links from game review and other tools keep working."
              className="border-none bg-transparent p-0 shadow-none"
              contentClassName="grid gap-4 md:grid-cols-2 xl:grid-cols-4"
            >
              <ContextValueCard label="Game id" value={initialGameId || "Not provided"} description="Links the queued sideline back to the originating game when available." />
              <ContextValueCard label="Move ply" value={resolvedMovePly ?? "Not provided"} description="Keeps move-level context aligned with the source position used to seed analysis." />
              <ContextValueCard label="Starting FEN" value={initialFen || "Default starting position"} description="The board opens from this exact position when a FEN is supplied." breakValue />
              <ContextValueCard label="Branch moves" value={initialBranchMoves || "Not provided"} description="Candidate UCI moves continue to prefill the sideline queue form for quick iteration." breakValue />
            </DetailPane>
          )}
          aside={(
            <UtilityPanelStack>
              <UtilityPanel
                eyebrow="Contextual tool"
                title="Create sideline from custom position"
                description="Queue the same sideline workflow from the rail so the board remains the dominant surface."
              >
                <SidelineAnalysisForm
                  title="Create sideline from custom position"
                  initialGameId={initialGameId}
                  initialMovePly={resolvedMovePly}
                  initialFen={initialFen}
                  initialBranchMoves={initialBranchMoves}
                />
              </UtilityPanel>
              <UtilityPanel
                eyebrow="Move summary"
                title="Deep-link payload"
                description="Route parameters stay visible in a lighter-weight stack so support modules do not overpower the analysis board."
              >
                <UtilityPanelGroup>
                  <div className="grid gap-2 text-sm text-muted-foreground">
                    <div className="flex items-start justify-between gap-3 rounded-lg border border-border/55 bg-background/55 px-3 py-2.5">
                      <span>Game id</span>
                      <span className="text-right font-medium text-foreground">{initialGameId || "Not provided"}</span>
                    </div>
                    <div className="flex items-start justify-between gap-3 rounded-lg border border-border/55 bg-background/55 px-3 py-2.5">
                      <span>Move ply</span>
                      <span className="text-right font-medium text-foreground">{resolvedMovePly ?? "Not provided"}</span>
                    </div>
                    <div className="flex items-start justify-between gap-3 rounded-lg border border-border/55 bg-background/55 px-3 py-2.5">
                      <span>Branch moves</span>
                      <span className="break-all text-right font-medium text-foreground">{initialBranchMoves || "Not provided"}</span>
                    </div>
                  </div>
                </UtilityPanelGroup>
              </UtilityPanel>
            </UtilityPanelStack>
          )}
        />
      </PageSection>
    </PageContainer>
  );
}
