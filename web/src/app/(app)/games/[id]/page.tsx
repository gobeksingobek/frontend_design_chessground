import Link from "next/link";

import { GameDetail } from "@/components/games/game-detail";

export default function GameDetailsPage({ params, searchParams }: { params: { id: string }; searchParams?: { ply?: string } }) {
  const gameId = Number(params.id);
  const requestedPly = searchParams?.ply ? Number(searchParams.ply) : null;
  const initialPly = requestedPly !== null && Number.isFinite(requestedPly) && requestedPly > 0 ? requestedPly : null;

  if (!Number.isFinite(gameId)) {
    return (
      <div className="stack">
        <h2>Game details</h2>
        <p>Invalid game id.</p>
      </div>
    );
  }

  return (
    <div className="stack">
      <div>
        <Link href="/games">← Back to games</Link>
      </div>
      <h2>Game #{gameId}</h2>
      <GameDetail gameId={gameId} initialPly={initialPly} />
    </div>
  );
}
