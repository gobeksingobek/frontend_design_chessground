import { GamesTable } from "@/components/games/games-table";

export default function GamesPage() {
  return (
    <div className="stack">
      <h2>Games</h2>
      <p>Phase 2: live games list from backend read API.</p>
      <GamesTable />
    </div>
  );
}
