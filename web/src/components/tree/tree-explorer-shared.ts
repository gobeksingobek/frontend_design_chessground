export interface CanonicalTreeSnapshot {
  posId: number;
  coveragePct: number;
  repertoireCount: number;
  gameCount: number;
}

interface TreeContractShape {
  pos_id?: number;
  coverage_pct?: number;
  repertoire_children?: unknown[];
  game_children?: unknown[];
}

export function toCanonicalTreeSnapshot(
  browse?: TreeContractShape | null,
  coverage?: TreeContractShape | null,
  metrics?: TreeContractShape | null,
): CanonicalTreeSnapshot {
  const source = browse ?? coverage ?? metrics;
  return {
    posId: Number(source?.pos_id ?? 1),
    coveragePct: Number(coverage?.coverage_pct ?? 0),
    repertoireCount: Number((browse?.repertoire_children ?? coverage?.repertoire_children ?? metrics?.repertoire_children ?? []).length),
    gameCount: Number((browse?.game_children ?? coverage?.game_children ?? metrics?.game_children ?? []).length),
  };
}
