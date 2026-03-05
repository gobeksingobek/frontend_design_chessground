"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ChessBoard } from "@/components/chess/chess-board";
import { getTreeExplorer } from "@/lib/api-client";

export function TreeExplorer() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["tree", "explorer"],
    queryFn: getTreeExplorer,
  });
  const nodes = useMemo(() => data?.nodes ?? [], [data]);

  const defaultNodeId = nodes[0]?.id ?? null;
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const selectedNode = useMemo(() => {
    const activeId = selectedNodeId ?? defaultNodeId;
    return nodes.find((node) => node.id === activeId) ?? null;
  }, [nodes, defaultNodeId, selectedNodeId]);

  if (isLoading) return <p>Loading tree explorer...</p>;
  if (error) return <p className="warn">Failed to load tree explorer: {(error as Error).message}</p>;
  if (nodes.length === 0) return <p>No tree nodes yet. Queue analysis from Games or Analysis to populate your tree.</p>;

  return (
    <div className="board-page-layout">
      <div className="card">
        <h3>Selected node</h3>
        {selectedNode ? (
          <>
            <ChessBoard fen={selectedNode.fen} size="large" title={selectedNode.san_move ?? selectedNode.uci_move ?? "Root position"} />
            <p>
              Branch depth: <strong>{selectedNode.branch_depth}</strong> · Children: <strong>{selectedNode.child_count}</strong>
            </p>
          </>
        ) : (
          <p>Select a node to inspect the position.</p>
        )}
      </div>

      <div className="card menu-card">
        <h3>Node list</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Move</th>
              <th>Depth</th>
              <th>Branch</th>
              <th>Coverage</th>
            </tr>
          </thead>
          <tbody>
            {nodes.map((node) => (
              <tr
                key={node.id}
                className={selectedNode?.id === node.id ? "row-selected" : ""}
                onClick={() => setSelectedNodeId(node.id)}
              >
                <td>{node.san_move ?? node.uci_move ?? "Start"}</td>
                <td>{node.depth}</td>
                <td>{node.branch_depth}</td>
                <td>
                  <div className="coverage-cell">
                    <progress max={100} value={Math.max(0, Math.min(100, node.coverage))} />
                    <span>{node.coverage.toFixed(0)}%</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
