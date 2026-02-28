"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { createSideline, getGame } from "@/lib/api-client";

export function GameDetail({ gameId }: { gameId: number }) {
  const queryClient = useQueryClient();
  const [selectedPly, setSelectedPly] = useState<number | null>(null);
  const [branchMovesInput, setBranchMovesInput] = useState("");
  const [createdSideline, setCreatedSideline] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["game", gameId],
    queryFn: () => getGame(gameId),
  });

  const selectedMove = useMemo(() => {
    if (!data || selectedPly === null) return null;
    return data.moves.find((move) => move.ply === selectedPly) ?? null;
  }, [data, selectedPly]);

  const createSidelineMutation = useMutation({
    mutationFn: async () => {
      if (!selectedMove?.fen) {
        throw new Error("Selected move does not have an available FEN");
      }
      const branchMoves = branchMovesInput
        .split(/[\s,]+/)
        .map((item) => item.trim())
        .filter(Boolean);

      if (branchMoves.length === 0) {
        throw new Error("Enter at least one UCI move");
      }

      const idempotencyKey = `game-${gameId}-ply-${selectedMove.ply}-${Date.now()}`;
      return createSideline(
        {
          game_id: String(gameId),
          move_ply: selectedMove.ply,
          fen: selectedMove.fen,
          branch_moves: branchMoves,
        },
        idempotencyKey,
      );
    },
    onSuccess: (result) => {
      setCreatedSideline(result.id);
      queryClient.invalidateQueries({ queryKey: ["sidelines", 20] });
    },
  });

  if (isLoading) return <p>Loading game detail...</p>;
  if (error) return <p>Failed to load game detail: {(error as Error).message}</p>;

  return (
    <div className="stack">
      <div className="card">
        <h3>Header</h3>
        <pre className="code">{JSON.stringify(data?.header, null, 2)}</pre>
      </div>

      <div className="card">
        <h3>Create sideline analysis job</h3>
        <label>
          Move ply
          <select
            value={selectedPly ?? ""}
            onChange={(event) => setSelectedPly(event.target.value ? Number(event.target.value) : null)}
          >
            <option value="">Select a move...</option>
            {data?.moves.map((move) => (
              <option key={move.ply} value={move.ply}>
                Ply {move.ply} — {move.san_move ?? move.uci_move ?? "-"}
              </option>
            ))}
          </select>
        </label>

        <label>
          Branch moves (UCI, comma or whitespace separated)
          <input
            value={branchMovesInput}
            onChange={(event) => setBranchMovesInput(event.target.value)}
            placeholder="e2e4 e7e5 g1f3"
          />
        </label>

        <button type="button" onClick={() => createSidelineMutation.mutate()} disabled={createSidelineMutation.isPending}>
          {createSidelineMutation.isPending ? "Queueing..." : "Queue sideline"}
        </button>

        {selectedMove?.fen ? <small>Selected FEN: {selectedMove.fen}</small> : <small>Select a move to load FEN.</small>}
        {createSidelineMutation.isError ? <p>Failed: {(createSidelineMutation.error as Error).message}</p> : null}
        {createdSideline ? <p>Queued sideline request: {createdSideline}</p> : null}
      </div>

      <div className="card">
        <h3>Moves</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Ply</th>
              <th>SAN</th>
              <th>UCI</th>
              <th>Class</th>
              <th>Quality</th>
              <th>Your CPL</th>
            </tr>
          </thead>
          <tbody>
            {data?.moves.map((move) => (
              <tr key={move.ply}>
                <td>{move.ply}</td>
                <td>{move.san_move ?? "-"}</td>
                <td>{move.uci_move ?? "-"}</td>
                <td>{move.repertoire_class ?? "-"}</td>
                <td>{move.quality_label ?? "-"}</td>
                <td>{move.your_cpl ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
