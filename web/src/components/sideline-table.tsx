"use client";

import { useQuery } from "@tanstack/react-query";

import { listSidelines } from "@/lib/api-client";

export function SidelineTable() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["sidelines", 20],
    queryFn: () => listSidelines(20),
  });

  if (isLoading) {
    return <p>Loading sideline jobs...</p>;
  }

  if (error) {
    return <p>Failed to load sidelines: {(error as Error).message}</p>;
  }

  return (
    <table className="table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Game</th>
          <th>Ply</th>
          <th>Status</th>
          <th>Attempts</th>
        </tr>
      </thead>
      <tbody>
        {data?.map((row) => (
          <tr key={row.id}>
            <td>{row.id.slice(0, 8)}…</td>
            <td>{row.game_id}</td>
            <td>{row.move_ply}</td>
            <td>{row.status}</td>
            <td>{row.attempts}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
