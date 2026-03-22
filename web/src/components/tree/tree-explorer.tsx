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

  return (
    <TreeExplorerView
      layout={layout}
      posId={posId}
      onPosIdChange={setPosId}
      browse={browse}
      coverage={coverage}
      metrics={metrics}
      selectedMoveUci={resolvedSelectedMove}
      onSelectMove={setSelectedMoveUci}
      isLoading={isLoading}
      isError={isError}
      errorMessage={errorMessage}
    />
  );
}
