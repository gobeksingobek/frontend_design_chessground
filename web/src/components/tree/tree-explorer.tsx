"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getLineTreeBranchMetrics, getLineTreeBrowse, getLineTreeCoverage } from "@/lib/api-client";

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

export function TreeExplorer() {
  const [posId, setPosId] = useState(1);
  const browse = useQuery({ queryKey: ["tree", "browse", posId], queryFn: () => getLineTreeBrowse(posId, true) });
  const coverage = useQuery({ queryKey: ["tree", "coverage", posId], queryFn: () => getLineTreeCoverage(posId, true) });
  const metrics = useQuery({ queryKey: ["tree", "metrics", posId], queryFn: () => getLineTreeBranchMetrics(posId, true) });
  const canonical = toCanonicalTreeSnapshot(browse.data, coverage.data);

  return <div className="card"><input type="number" value={posId} onChange={(e)=>setPosId(Number(e.target.value)||1)} />Coverage {canonical.coveragePct.toFixed(1)}% · rep {canonical.repertoireCount} · games {canonical.gameCount} · top {metrics.data?.top_game_branches.length ?? 0}</div>;
}
