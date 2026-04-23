"use client";

import { TreeExplorerView, type TreeExplorerLayout } from "@/components/tree/tree-explorer-view";
import { useTreeExplorerData } from "@/components/tree/use-tree-explorer-data";

export type { TreeExplorerLayout } from "@/components/tree/tree-explorer-view";

export { toCanonicalTreeSnapshot } from "@/components/tree/tree-explorer-shared";

export function TreeExplorer({ layout = "workspace" }: { layout?: TreeExplorerLayout }) {
  const {
    posId,
    setPosId,
    browse,
    coverage,
    metrics,
    resolvedSelectedMove,
    setSelectedMoveUci,
    isLoading,
    isError,
    errorMessage,
  } = useTreeExplorerData();
  const adaptedBrowse = browse ?? (metrics
    ? {
      pos_id: metrics.pos_id,
      my_side_only: metrics.my_side_only,
      repertoire_children: metrics.repertoire_children,
      game_children: metrics.game_children,
    }
    : undefined);
  const adaptedCoverage = coverage ?? (metrics
    ? {
      pos_id: metrics.pos_id,
      my_side_only: metrics.my_side_only,
      repertoire_children: metrics.repertoire_children,
      game_children: metrics.game_children,
      total_repertoire_moves: metrics.repertoire_children.length,
      covered_by_games: 0,
      coverage_pct: 0,
    }
    : undefined);

  return (
    <TreeExplorerView
      layout={layout}
      posId={posId}
      onPosIdChange={setPosId}
      browse={adaptedBrowse}
      coverage={adaptedCoverage}
      metrics={metrics}
      selectedMoveUci={resolvedSelectedMove}
      onSelectMove={setSelectedMoveUci}
      isLoading={isLoading}
      isError={isError}
      errorMessage={errorMessage}
    />
  );
}
