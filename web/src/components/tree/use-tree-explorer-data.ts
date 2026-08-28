"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getLineTreeBranchMetrics, getLineTreeBrowse, getLineTreeCoverage, getPositionIntelligence } from "@/lib/api-client";
import type { PositionIntelligenceResponse, TreeBranchMetricsResponse, TreeBrowseResponse, TreeCoverageResponse } from "@/lib/types";

export interface UseTreeExplorerDataResult {
  posId: number;
  setPosId: (value: number) => void;
  selectedMoveUci: string | null;
  setSelectedMoveUci: (value: string | null) => void;
  browse: TreeBrowseResponse | undefined;
  coverage: TreeCoverageResponse | undefined;
  metrics: TreeBranchMetricsResponse | undefined;
  intelligence: PositionIntelligenceResponse | undefined;
  resolvedSelectedMove: string | null;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | null;
}

export function useTreeExplorerData(initialPosId = 1): UseTreeExplorerDataResult {
  const [posId, setPosIdState] = useState(initialPosId);
  const [selectedMoveUci, setSelectedMoveUci] = useState<string | null>(null);

  const browseQuery = useQuery({
    queryKey: ["tree", "browse", posId],
    queryFn: () => getLineTreeBrowse(posId, true),
  });
  const coverageQuery = useQuery({
    queryKey: ["tree", "coverage", posId],
    queryFn: () => getLineTreeCoverage(posId, true),
  });
  const metricsQuery = useQuery({
    queryKey: ["tree", "metrics", posId],
    queryFn: () => getLineTreeBranchMetrics(posId, true),
  });
  const intelligenceQuery = useQuery({
    queryKey: ["tree", "position-intelligence", posId],
    queryFn: () => getPositionIntelligence(posId, true),
  });

  const defaultSelectedMove = useMemo(
    () =>
      browseQuery.data?.repertoire_children.find((move) => move.is_user_mainline)?.uci_move
      ?? browseQuery.data?.repertoire_children[0]?.uci_move
      ?? null,
    [browseQuery.data],
  );

  const errorMessage = [browseQuery.error, coverageQuery.error, metricsQuery.error, intelligenceQuery.error]
    .find((error): error is Error => error instanceof Error)
    ?.message ?? null;

  return {
    posId,
    setPosId: (value: number) => {
      setPosIdState(value || 1);
      setSelectedMoveUci(null);
    },
    selectedMoveUci,
    setSelectedMoveUci,
    browse: browseQuery.data,
    coverage: coverageQuery.data,
    metrics: metricsQuery.data,
    intelligence: intelligenceQuery.data,
    resolvedSelectedMove: selectedMoveUci ?? defaultSelectedMove,
    isLoading: browseQuery.isLoading || coverageQuery.isLoading || metricsQuery.isLoading || intelligenceQuery.isLoading,
    isError: browseQuery.isError || coverageQuery.isError || metricsQuery.isError || intelligenceQuery.isError,
    errorMessage,
  };
}
