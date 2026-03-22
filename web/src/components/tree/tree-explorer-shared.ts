export interface CanonicalTreeSnapshot {
  posId: number;
  coveragePct: number;
  repertoireCount: number;
  gameCount: number;
}

export function toCanonicalTreeSnapshot(browse: any, coverage: any): CanonicalTreeSnapshot {
  return {
    posId: Number(browse?.pos_id ?? coverage?.pos_id ?? 1),
    coveragePct: Number(coverage?.coverage_pct ?? 0),
    repertoireCount: Number(browse?.repertoire_children?.length ?? 0),
    gameCount: Number(browse?.game_children?.length ?? 0),
  };
}
