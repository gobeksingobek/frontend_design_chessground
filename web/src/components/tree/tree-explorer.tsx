"use client";

import { toCanonicalTreeContract, toCanonicalTreeSnapshot } from "@/components/tree/tree-explorer-shared";
import { TreeExplorerView, type TreeExplorerLayout } from "@/components/tree/tree-explorer-view";
import { useTreeExplorerData } from "@/components/tree/use-tree-explorer-data";

export type { TreeExplorerLayout } from "@/components/tree/tree-explorer-view";

export { toCanonicalTreeSnapshot } from "@/components/tree/tree-explorer-shared";

export function TreeExplorer({ layout = "workspace" }: { layout?: TreeExplorerLayout }) {
  const { posId, setPosId, browse, coverage, metrics, resolvedSelectedMove, setSelectedMoveUci, isLoading, isError, errorMessage } = useTreeExplorerData();
  const canonical = toCanonicalTreeContract({ browse, coverage, metrics });

  return (
    <TreeExplorerView
      layout={layout}
      posId={posId || toCanonicalTreeSnapshot(canonical.browse, canonical.coverage, canonical.metrics).posId}
      onPosIdChange={setPosId}
      browse={canonical.browse}
      coverage={canonical.coverage}
      metrics={canonical.metrics}
      selectedMoveUci={resolvedSelectedMove}
      onSelectMove={setSelectedMoveUci}
      isLoading={isLoading}
      isError={isError}
      errorMessage={errorMessage}
    />
  );
}
