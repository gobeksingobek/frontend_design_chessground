"use client";

import { RepertoireTree } from "@/components/tree/repertoire-tree";
import { toCanonicalTreeSnapshot } from "@/components/tree/tree-explorer-shared";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { BodyText, CardTitle, MutedText } from "@/components/ui/typography";
import type { TreeBranchMetricsResponse, TreeBrowseResponse, TreeCoverageResponse } from "@/lib/types";
import { cn } from "@/lib/cn";

export type TreeExplorerLayout = "workspace" | "utility" | "stacked";

const layoutCardVariant = {
  workspace: "workspace",
  utility: "utility",
  stacked: "soft",
} as const;

const layoutTreeClassName = {
  workspace: "",
  utility: "gap-4",
  stacked: "gap-4",
} as const;

export function TreeExplorerView({
  posId,
  onPosIdChange,
  browse,
  coverage,
  metrics,
  selectedMoveUci,
  onSelectMove,
  isLoading,
  isError,
  errorMessage,
  layout = "workspace",
}: {
  posId: number;
  onPosIdChange: (value: number) => void;
  browse?: TreeBrowseResponse;
  coverage?: TreeCoverageResponse;
  metrics?: TreeBranchMetricsResponse;
  selectedMoveUci?: string | null;
  onSelectMove?: (uciMove: string | null) => void;
  isLoading?: boolean;
  isError?: boolean;
  errorMessage?: string | null;
  layout?: TreeExplorerLayout;
}) {
  const canonical = toCanonicalTreeSnapshot(browse, coverage);
  const hasBranches = Boolean(browse && (browse.repertoire_children.length > 0 || browse.game_children.length > 0));

  return (
    <div className="grid gap-4">
      <Card variant={layoutCardVariant[layout]} className={cn(layout === "stacked" && "gap-4 px-lg py-lg")}>
        <div className={cn("grid gap-3", layout === "utility" && "gap-2")}>
          <div className="grid gap-1">
            <CardTitle className="text-base sm:text-lg">Tree explorer</CardTitle>
            <MutedText className="text-sm leading-6">
              This presentation layer stays aligned with the existing browse, coverage, and metrics payloads while adapting to workspace, rail, or stacked layouts.
            </MutedText>
          </div>

          <label className={cn("grid gap-2 text-sm text-muted-foreground", layout === "utility" ? "max-w-full" : "max-w-xs")}>
            Position id
            <Input
              type="number"
              value={posId}
              onChange={(event) => onPosIdChange(Number(event.target.value) || 1)}
            />
          </label>

          <div className={cn("flex flex-wrap gap-x-4 gap-y-2", layout === "stacked" && "grid gap-2")}>
            <BodyText className="text-sm">Coverage {canonical.coveragePct.toFixed(1)}%</BodyText>
            <BodyText className="text-sm">Repertoire {canonical.repertoireCount}</BodyText>
            <BodyText className="text-sm">Games {canonical.gameCount}</BodyText>
            <BodyText className="text-sm">Top branches {metrics?.top_game_branches.length ?? 0}</BodyText>
          </div>
        </div>
      </Card>

      {isLoading ? (
        <Card variant="soft" className="gap-4">
          <Skeleton className="h-6 w-40 rounded-lg" />
          <Skeleton className="h-24 w-full rounded-2xl" />
          <div className="grid gap-3">
            {Array.from({ length: layout === "utility" ? 2 : 3 }).map((_, index) => (
              <Skeleton key={index} className="h-28 w-full rounded-2xl" />
            ))}
          </div>
        </Card>
      ) : null}

      {!isLoading && isError ? (
        <EmptyState
          title="Unable to load tree data"
          description={errorMessage ?? "The current tree endpoints did not return a usable response for this position."}
        />
      ) : null}

      {!isLoading && !isError && browse && hasBranches ? (
        <RepertoireTree
          browse={browse}
          coverage={coverage}
          metrics={metrics}
          selectedMoveUci={selectedMoveUci}
          onSelectMove={(uciMove) => onSelectMove?.(uciMove)}
          className={layoutTreeClassName[layout]}
        />
      ) : null}

      {!isLoading && !isError && browse && !hasBranches ? (
        <EmptyState
          title="No branches available"
          description="The current tree payload does not expose repertoire or game rows for this position yet."
        />
      ) : null}
    </div>
  );
}
