import type { PositionIntelligenceResponse, TreeBranchMetricsResponse, TreeBrowseResponse, TreeCoverageResponse } from "@/lib/types";

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

export interface PositionIntelligenceSnapshot {
  posId: number;
  coveragePct: number;
  repertoireMoveCount: number;
  gameMoveCount: number;
  recentGameCount: number;
  hasEvidence: boolean;
}

export interface PositionIntelligencePanelState {
  status: "loading" | "empty" | "ready";
  topRepertoireMoves: string[];
  topGameMoves: string[];
  matters: string[];
  recentGameLabels: string[];
}

export function toNavigablePositionId(value: number | null | undefined): number | null {
  const posId = Number(value);
  return Number.isInteger(posId) && posId > 0 ? posId : null;
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

export function toPositionIntelligenceSnapshot(intelligence?: PositionIntelligenceResponse | null): PositionIntelligenceSnapshot {
  return {
    posId: Number(intelligence?.pos_id ?? 1),
    coveragePct: Number(intelligence?.coverage.coverage_pct ?? 0),
    repertoireMoveCount: Number(intelligence?.repertoire_continuations.length ?? 0),
    gameMoveCount: Number(intelligence?.game_continuations.length ?? 0),
    recentGameCount: Number(intelligence?.recent_games.length ?? 0),
    hasEvidence: Boolean(
      (intelligence?.repertoire_continuations.length ?? 0) > 0
      || (intelligence?.game_continuations.length ?? 0) > 0
      || (intelligence?.recent_games.length ?? 0) > 0
      || (intelligence?.evidence.matters.length ?? 0) > 0,
    ),
  };
}

export function toPositionIntelligencePanelState(
  intelligence?: PositionIntelligenceResponse | null,
): PositionIntelligencePanelState {
  if (!intelligence) {
    return {
      status: "loading",
      topRepertoireMoves: [],
      topGameMoves: [],
      matters: [],
      recentGameLabels: [],
    };
  }

  const hasEvidence = toPositionIntelligenceSnapshot(intelligence).hasEvidence;
  return {
    status: hasEvidence ? "ready" : "empty",
    topRepertoireMoves: intelligence.repertoire_continuations
      .slice(0, 3)
      .map((move) => `${move.san_move ?? move.uci_move} (${move.weight})`),
    topGameMoves: intelligence.game_continuations
      .slice(0, 3)
      .map((move) => `${move.san_move ?? move.uci_move} (${move.games})`),
    matters: intelligence.evidence.matters.slice(0, 3),
    recentGameLabels: intelligence.recent_games
      .slice(0, 3)
      .map((game) => `Game #${game.game_id} ply ${game.ply}: ${game.san_move ?? game.uci_move ?? "-"} - ${game.result ?? "no result"}`),
  };
}
