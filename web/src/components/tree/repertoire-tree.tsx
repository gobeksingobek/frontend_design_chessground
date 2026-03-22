"use client";

import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { BodyText, CaptionText, CardTitle, FieldLabel, MonoText, MutedText } from "@/components/ui/typography";
import { cn } from "@/lib/cn";
import type { TreeBranchMetricsResponse, TreeBrowseMove, TreeBrowseResponse, TreeCoverageResponse, TreeGameMove } from "@/lib/types";

type RepertoireTreeRow = {
  key: string;
  moveLabel: string;
  uciMove: string | null;
  nextPosId: number | null;
  metadata: Array<{ label: string; value: string }>;
  badges: Array<{ label: string; tone: "neutral" | "accent" | "success" | "warning" }>;
};

type RepertoireTreeGroup = {
  id: string;
  title: string;
  description: string;
  rows: RepertoireTreeRow[];
};

function formatNumber(value: number | null | undefined, suffix = "") {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return `${value}${suffix}`;
}

function buildRepertoireRows(moves: TreeBrowseMove[]): RepertoireTreeRow[] {
  return moves.map((move) => ({
    key: `rep-${move.uci_move}`,
    moveLabel: move.san_move ?? move.uci_move,
    uciMove: move.uci_move,
    nextPosId: move.next_pos_id,
    metadata: [
      { label: "Weight", value: formatNumber(move.weight) },
      { label: "Next pos", value: formatNumber(move.next_pos_id) },
    ],
    badges: [
      ...(move.is_user_mainline ? [{ label: "Current path", tone: "accent" as const }] : []),
      ...(move.is_priority_edge ? [{ label: "Priority", tone: "success" as const }] : []),
      ...(move.is_sideline_pending ? [{ label: "Pending", tone: "warning" as const }] : []),
    ],
  }));
}

function buildGameRows(moves: TreeGameMove[]): RepertoireTreeRow[] {
  return moves.map((move) => ({
    key: `game-${move.uci_move}`,
    moveLabel: move.san_move ?? move.uci_move,
    uciMove: move.uci_move,
    nextPosId: move.next_pos_id,
    metadata: [
      { label: "Games", value: formatNumber(move.games) },
      { label: "Score", value: formatNumber(Math.round(move.score_pct), "%") },
      { label: "Avg opp", value: formatNumber(move.avg_opp_elo) },
      { label: "W-D-L", value: `${move.wins}-${move.draws}-${move.losses}` },
    ],
    badges: [],
  }));
}

export function RepertoireTree({
  browse,
  coverage,
  metrics,
  selectedMoveUci,
  onSelectMove,
  className,
}: {
  browse: TreeBrowseResponse;
  coverage?: TreeCoverageResponse | null;
  metrics?: TreeBranchMetricsResponse | null;
  selectedMoveUci?: string | null;
  onSelectMove?: (uciMove: string) => void;
  className?: string;
}) {
  const groups = useMemo<RepertoireTreeGroup[]>(() => {
    const repertoireRows = buildRepertoireRows(browse.repertoire_children);
    const gameRows = buildGameRows(metrics?.top_game_branches?.length ? metrics.top_game_branches : browse.game_children);

    return [
      {
        id: "repertoire",
        title: "Repertoire branches",
        description: "Primary move tree from the existing browse payload.",
        rows: repertoireRows,
      },
      {
        id: "games",
        title: metrics?.top_game_branches?.length ? "Observed game branches" : "Game coverage",
        description: metrics?.top_game_branches?.length
          ? "Top played continuations from branch metrics."
          : "Observed continuations from the current browse response.",
        rows: gameRows,
      },
    ].filter((group) => group.rows.length > 0);
  }, [browse.game_children, browse.repertoire_children, metrics?.top_game_branches]);

  const summaryBadges = [
    { label: `${browse.repertoire_children.length} repertoire`, tone: "accent" as const },
    { label: `${browse.game_children.length} game branches`, tone: "neutral" as const },
    ...(coverage ? [{ label: `${coverage.coverage_pct.toFixed(1)}% covered`, tone: "success" as const }] : []),
  ];

  return (
    <Card variant="soft" className={cn("gap-5 border-border/70 bg-elevated/80", className)}>
      <div className="grid gap-3 border-b border-border/60 pb-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="grid gap-1">
            <CaptionText>Repertoire tree</CaptionText>
            <CardTitle className="text-base sm:text-lg">Scan branch structure beneath the board</CardTitle>
            <MutedText className="max-w-3xl text-sm leading-6">
              The component stays presentational and adapts directly to the existing tree browse, coverage, and metrics payloads.
            </MutedText>
          </div>
          <div className="flex flex-wrap gap-2">
            {summaryBadges.map((badge) => (
              <Badge key={badge.label} tone={badge.tone}>{badge.label}</Badge>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-border/70 bg-card/80 px-4 py-4 shadow-soft">
          <div className="flex items-start gap-4">
            <div className="mt-1 h-3 w-3 rounded-full border border-primary/40 bg-primary/80 shadow-[0_0_0_4px_rgba(var(--color-primary),0.12)]" />
            <div className="grid flex-1 gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <FieldLabel as="span">Root move</FieldLabel>
                <BodyText as="span" className="font-medium text-foreground">Position {browse.pos_id}</BodyText>
                <Badge tone="accent" variant="outline">Current position</Badge>
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-muted-foreground">
                <span>My side only: {browse.my_side_only ? "Yes" : "No"}</span>
                {coverage ? <span>Covered by games: {coverage.covered_by_games}/{coverage.total_repertoire_moves}</span> : null}
                <span>Top repertoire branches: {metrics?.top_repertoire_branches?.length ?? browse.repertoire_children.length}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-5">
        {groups.map((group) => (
          <section key={group.id} className="grid gap-3">
            <div className="grid gap-1">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">{group.title}</CardTitle>
                <Badge variant="outline">{group.rows.length}</Badge>
              </div>
              <MutedText className="text-sm leading-6">{group.description}</MutedText>
            </div>

            <div className="grid gap-0">
              {group.rows.map((row, index) => {
                const isSelected = selectedMoveUci ? row.uciMove === selectedMoveUci : row.badges.some((badge) => badge.label === "Current path");
                const isLast = index === group.rows.length - 1;
                const interactive = Boolean(onSelectMove && row.uciMove);

                return (
                  <div key={row.key} className="relative pl-8">
                    <div className={cn("absolute left-3 top-0 w-px bg-border/70", isLast ? "h-6" : "bottom-0")}/>
                    <div className={cn("absolute left-3 top-6 h-px w-4 bg-border/70", isSelected && "bg-primary/60")}/>
                    <div className={cn("absolute left-[9px] top-[20px] h-3 w-3 rounded-full border bg-background", isSelected ? "border-primary bg-primary/90 shadow-[0_0_0_4px_rgba(var(--color-primary),0.12)]" : "border-border bg-card")}/>

                    <button
                      type="button"
                      disabled={!interactive}
                      onClick={() => row.uciMove && onSelectMove?.(row.uciMove)}
                      className={cn(
                        "grid w-full gap-3 rounded-2xl border px-4 py-4 text-left transition",
                        "border-border/70 bg-card/75 hover:bg-hover",
                        interactive ? "cursor-pointer" : "cursor-default",
                        isSelected && "border-primary/40 bg-selection text-selection-foreground shadow-soft",
                        !interactive && "disabled:opacity-100",
                      )}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="grid gap-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <BodyText as="span" className={cn("font-semibold", isSelected ? "text-selection-foreground" : "text-foreground")}>{row.moveLabel}</BodyText>
                            {row.uciMove ? <MonoText className={cn("text-xs", isSelected ? "text-selection-foreground/80" : "text-muted-foreground")}>{row.uciMove}</MonoText> : null}
                          </div>
                          <MutedText className={cn("text-sm leading-6", isSelected ? "text-selection-foreground/80" : "text-muted-foreground")}>
                            {row.nextPosId ? `Continues to position ${row.nextPosId}.` : "No linked downstream position is exposed for this branch."}
                          </MutedText>
                        </div>
                        {row.badges.length > 0 ? (
                          <div className="flex flex-wrap justify-end gap-2">
                            {row.badges.map((badge) => (
                              <Badge key={`${row.key}-${badge.label}`} tone={badge.tone}>{badge.label}</Badge>
                            ))}
                          </div>
                        ) : null}
                      </div>

                      <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        {row.metadata.map((item) => (
                          <div key={`${row.key}-${item.label}`} className={cn("rounded-xl border px-3 py-3", isSelected ? "border-primary/20 bg-background/20" : "border-border/60 bg-background/40")}>
                            <dt><CaptionText>{item.label}</CaptionText></dt>
                            <dd className="mt-2 text-sm font-medium text-foreground">{item.value}</dd>
                          </div>
                        ))}
                      </dl>
                    </button>
                  </div>
                );
              })}
            </div>
          </section>
        ))}

        {groups.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/70 bg-card/50 px-4 py-6 text-center">
            <CardTitle className="text-base">No branches available</CardTitle>
            <MutedText className="mt-2 text-sm">The current tree payload does not expose repertoire or game rows for this position yet.</MutedText>
          </div>
        ) : null}
      </div>
    </Card>
  );
}
