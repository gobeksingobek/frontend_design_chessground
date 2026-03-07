"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getLineTreeBranchMetrics, getLineTreeBrowse, getLineTreeCoverage } from "@/lib/api-client";

export function TreeExplorer() {
  const [posId, setPosId] = useState(1);
  const browse = useQuery({ queryKey: ["tree", "browse", posId], queryFn: () => getLineTreeBrowse(posId, true) });
  const coverage = useQuery({ queryKey: ["tree", "coverage", posId], queryFn: () => getLineTreeCoverage(posId, true) });
  const metrics = useQuery({ queryKey: ["tree", "metrics", posId], queryFn: () => getLineTreeBranchMetrics(posId, true) });

  if (browse.isLoading) return <p>Loading tree explorer...</p>;
  if (browse.error) return <p className="warn">Failed to load tree explorer: {(browse.error as Error).message}</p>;

  return (
    <div className="stack">
      <div className="card">
        <label>
          Position ID
          <input type="number" min={1} value={posId} onChange={(e) => setPosId(Number(e.target.value) || 1)} />
        </label>
        <p>
          Coverage: <strong>{coverage.data?.covered_by_games ?? 0}</strong> / <strong>{coverage.data?.total_repertoire_moves ?? 0}</strong>
          {" "}({(coverage.data?.coverage_pct ?? 0).toFixed(1)}%)
        </p>
      </div>

      <div className="card menu-card">
        <h3>Repertoire children</h3>
        <table className="table">
          <thead><tr><th>Move</th><th>Weight</th><th>Next pos</th><th>Flags</th></tr></thead>
          <tbody>
            {(browse.data?.repertoire_children ?? []).map((move) => (
              <tr key={`${move.uci_move}-${move.next_pos_id ?? "none"}`}>
                <td>{move.san_move ?? move.uci_move}</td>
                <td>{move.weight}</td>
                <td>{move.next_pos_id ?? "-"}</td>
                <td>{move.is_user_mainline ? "mainline " : ""}{move.is_priority_edge ? "priority " : ""}{move.is_sideline_pending ? "pending" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card menu-card">
        <h3>Top game branches</h3>
        <table className="table">
          <thead><tr><th>Move</th><th>Games</th><th>Score %</th></tr></thead>
          <tbody>
            {(metrics.data?.top_game_branches ?? []).map((move) => (
              <tr key={`${String(move.uci_move)}-${String(move.next_pos_id ?? "none")}`}>
                <td>{String(move.san_move ?? move.uci_move ?? "-")}</td>
                <td>{String(move.games ?? "0")}</td>
                <td>{String(move.score_pct ?? "0")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
