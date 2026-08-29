import { PageContainer, PageSection } from "@/components/app-shell";
import { GameDetail } from "@/components/games/game-detail";
import { SectionHeader } from "@/components/ui/section-header";

function readSingleParam(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

function parseSelectedPly(value: string | undefined): number | null {
  if (!value) return null;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) return null;
  return parsed;
}

export default async function GameDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ ply?: string | string[]; tab?: string | string[]; orientation?: string | string[] }>;
}) {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  const gameId = Number(id);
  const plyParam = readSingleParam(query.ply);
  const tabParam = readSingleParam(query.tab);
  const orientationParam = readSingleParam(query.orientation);
  const initialPly = parseSelectedPly(plyParam);
  const initialTab = tabParam === "moves" ? "moves" : "board";
  const initialOrientation = orientationParam === "black" ? "black" : "white";
  if (!Number.isFinite(gameId)) return <p className="text-sm text-danger">Invalid game id.</p>;
  return <PageContainer title={`Game ${gameId}`} description="Inspect move quality, evaluation changes, and sideline opportunities for a single game."><PageSection><SectionHeader title={`Game ${gameId}`} description="Inspect move quality, evaluation changes, and sideline opportunities." /><GameDetail key={`game-${gameId}`} gameId={gameId} initialPly={initialPly} initialTab={initialTab} initialOrientation={initialOrientation} /></PageSection></PageContainer>;
}
