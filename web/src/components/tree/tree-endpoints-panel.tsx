"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getLineTreeBranchMetrics, getLineTreeBrowse, getLineTreeCoverage } from "@/lib/api-client";

export function TreeEndpointsPanel() {
  const [posId, setPosId] = useState(1);

  const browse = useQuery({ queryKey: ["line-tree", "browse", posId], queryFn: () => getLineTreeBrowse(posId, true) });
  const coverage = useQuery({ queryKey: ["line-tree", "coverage", posId], queryFn: () => getLineTreeCoverage(posId, true) });
  const metrics = useQuery({ queryKey: ["line-tree", "metrics", posId], queryFn: () => getLineTreeBranchMetrics(posId, true) });

  return (
    <div className="card">
      <h3>Tree endpoint explorer</h3>
      <label>
        Position ID
        <input type="number" min={1} value={posId} onChange={(e) => setPosId(Number(e.target.value) || 1)} />
      </label>
      {coverage.data ? (
        <p>
          Coverage: <strong>{coverage.data.covered_by_games}</strong> / <strong>{coverage.data.total_repertoire_moves}</strong> ({coverage.data.coverage_pct.toFixed(1)}%)
        </p>
      ) : null}
      {browse.data ? <p>Repertoire moves: {browse.data.repertoire_children.length} · Game moves: {browse.data.game_children.length}</p> : null}
      {metrics.data ? <p>Top branches: repertoire {metrics.data.top_repertoire_branches.length}, games {metrics.data.top_game_branches.length}</p> : null}
      {browse.error || coverage.error || metrics.error ? <p className="warn">Failed to load tree endpoint data.</p> : null}
    </div>
  );
}
