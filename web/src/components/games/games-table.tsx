"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { listGames } from "@/lib/api-client";

export function GamesTable() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["games", 50, 0],
    queryFn: () => listGames(50, 0),
  });

  if (isLoading) return <p>Loading games...</p>;
  if (error) return <p>Failed to load games: {(error as Error).message}</p>;

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Date</th>
          <th>White</th>
          <th>Black</th>
          <th>Result</th>
          <th>Compliance</th>
          <th>Line</th>
          <th>Details</th>
        </tr>
      </thead>
      <tbody>
        {data?.map((game) => (
          <tr key={game.id}>
            <td>{game.date ?? "-"}</td>
            <td>{game.white ?? "-"}</td>
            <td>{game.black ?? "-"}</td>
            <td>{game.result ?? "-"}</td>
            <td>{game.compliance ?? "-"}</td>
            <td>{game.line_id ?? "-"}</td>
            <td>
              <Link href={`/games/${game.id}`}>Open</Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
