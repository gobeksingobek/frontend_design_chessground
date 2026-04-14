import { PageContainer, PageSection } from "@/components/app-shell";
import { GameDetail } from "@/components/games/game-detail";
import { SectionHeader } from "@/components/ui/section-header";

function readSingleParam(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

export default function GameDetailPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams: { ply?: string | string[]; tab?: string | string[]; orientation?: string | string[] };
}) {
  const gameId = Number(params.id);
  const plyParam = readSingleParam(searchParams.ply);
  const tabParam = readSingleParam(searchParams.tab);
  const orientationParam = readSingleParam(searchParams.orientation);
  const initialPly = plyParam ? Number(plyParam) : null;
  const initialTab = tabParam === "moves" ? "moves" : "board";
  const initialOrientation = orientationParam === "black" ? "black" : "white";
  if (!Number.isFinite(gameId)) return <p className="text-sm text-danger">Invalid game id.</p>;
  return <PageContainer title={`Game ${gameId}`} description="Inspect move quality, evaluation changes, and sideline opportunities for a single game."><PageSection><SectionHeader title={`Game ${gameId}`} description="Inspect move quality, evaluation changes, and sideline opportunities." /><GameDetail key={`game-${gameId}`} gameId={gameId} initialPly={Number.isFinite(initialPly) ? initialPly : null} initialTab={initialTab} initialOrientation={initialOrientation} /></PageSection></PageContainer>;
}
