"use client";

import { useQuery } from "@tanstack/react-query";

import { getGame } from "@/lib/api-client";

export function GameDetail({ gameId }: { gameId: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["game", gameId],
    queryFn: () => getGame(gameId),
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
