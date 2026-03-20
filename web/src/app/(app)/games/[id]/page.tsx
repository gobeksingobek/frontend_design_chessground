import { PageContainer, PageSection } from "@/components/app-shell";
import { GameDetail } from "@/components/games/game-detail";
import { SectionHeader } from "@/components/ui/section-header";

export default function GameDetailPage({ params, searchParams }: { params: { id: string }; searchParams: { ply?: string }; }) {
  const gameId = Number(params.id);
  const initialPly = searchParams.ply ? Number(searchParams.ply) : null;
  if (!Number.isFinite(gameId)) return <p className="text-sm text-danger">Invalid game id.</p>;
  return <PageContainer title={`Game ${gameId}`} description="Inspect move quality, evaluation changes, and sideline opportunities for a single game."><PageSection><SectionHeader title={`Game ${gameId}`} description="Inspect move quality, evaluation changes, and sideline opportunities." /><GameDetail gameId={gameId} initialPly={Number.isFinite(initialPly) ? initialPly : null} /></PageSection></PageContainer>;
}
