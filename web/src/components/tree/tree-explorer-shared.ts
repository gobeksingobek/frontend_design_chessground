import type { TreeBranchMetricsResponse, TreeBrowseResponse, TreeCoverageResponse } from "@/lib/types";

export interface CanonicalTreeSnapshot {
  posId: number;
  coveragePct: number;
  repertoireCount: number;
  gameCount: number;
}

export interface CanonicalTreeContract {
  browse?: TreeBrowseResponse;
  coverage?: TreeCoverageResponse;
  metrics?: TreeBranchMetricsResponse;
}

export function toCanonicalTreeContract(contract: CanonicalTreeContract): Required<CanonicalTreeContract> {
  const fallbackSource = contract.browse ?? contract.coverage ?? contract.metrics;
  const posId = Number(fallbackSource?.pos_id ?? 1);
  const mySideOnly = Boolean(fallbackSource?.my_side_only ?? true);
  const repertoireChildren = contract.browse?.repertoire_children ?? contract.coverage?.repertoire_children ?? contract.metrics?.repertoire_children ?? [];
  const gameChildren = contract.browse?.game_children ?? contract.coverage?.game_children ?? contract.metrics?.game_children ?? [];

  const browse = contract.browse ?? {
    pos_id: posId,
    my_side_only: mySideOnly,
    repertoire_children: repertoireChildren,
    game_children: gameChildren,
  };
  const coverage = contract.coverage ?? {
    pos_id: posId,
    my_side_only: mySideOnly,
    repertoire_children: repertoireChildren,
    game_children: gameChildren,
    total_repertoire_moves: repertoireChildren.length,
    covered_by_games: 0,
    coverage_pct: 0,
  };
  const metrics = contract.metrics ?? {
    pos_id: posId,
    my_side_only: mySideOnly,
    repertoire_children: repertoireChildren,
    game_children: gameChildren,
    top_repertoire_branches: repertoireChildren.slice(0, 10),
    top_game_branches: gameChildren.slice(0, 10),
  };

  return { browse, coverage, metrics };
}

export function toCanonicalTreeSnapshot(
  browse?: TreeBrowseResponse | null,
  coverage?: TreeCoverageResponse | null,
  metrics?: TreeBranchMetricsResponse | null,
): CanonicalTreeSnapshot {
  const canonical = toCanonicalTreeContract({ browse: browse ?? undefined, coverage: coverage ?? undefined, metrics: metrics ?? undefined });
  return {
    posId: Number(canonical.browse.pos_id ?? 1),
    coveragePct: Number(canonical.coverage.coverage_pct ?? 0),
    repertoireCount: Number(canonical.browse.repertoire_children.length),
    gameCount: Number(canonical.browse.game_children.length),
  };
}
