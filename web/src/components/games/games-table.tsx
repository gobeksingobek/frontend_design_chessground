"use client";

import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { listGamesFiltered } from "@/lib/api-client";

export interface GamesTableState {
  result: string;
  compliance: string;
  complianceMin: string;
  lineId: string;
  player: string;
  dateFrom: string;
  dateTo: string;
  sortBy: "date" | "result" | "compliance" | "id";
  sortDir: "asc" | "desc";
}

export const DEFAULT_GAMES_TABLE_STATE: GamesTableState = {
  result: "",
  compliance: "",
  complianceMin: "",
  lineId: "",
  player: "",
  dateFrom: "",
  dateTo: "",
  sortBy: "date",
  sortDir: "desc",
};

export function applyStoredGamesTableState(parsed: Partial<GamesTableState>): GamesTableState {
  return { ...DEFAULT_GAMES_TABLE_STATE, ...parsed };
}

export function buildGamesQueryKey(state: GamesTableState): string[] {
  return ["games", ...Object.values(state)];
}

export function GamesTable({ state, onStateChange }: { state: GamesTableState; onStateChange: (next: GamesTableState) => void }) {
  useEffect(() => {
    localStorage.setItem("cg_games_table_state_v2", JSON.stringify(state));
  }, [state]);

  const queryKey = useMemo(() => buildGamesQueryKey(state), [state]);
  const { data, isLoading, error } = useQuery({
    queryKey,
    queryFn: () =>
      listGamesFiltered({
        limit: 200,
        result: state.result || undefined,
        compliance: state.compliance || undefined,
        complianceMin: state.complianceMin || undefined,
        lineId: state.lineId || undefined,
        player: state.player || undefined,
        dateFrom: state.dateFrom || undefined,
        dateTo: state.dateTo || undefined,
        sortBy: state.sortBy,
        sortDir: state.sortDir,
      }),
  });

  if (isLoading) return <p>Loading games...</p>;
  if (error) return <p>Failed to load games: {(error as Error).message}</p>;

  const set = (patch: Partial<GamesTableState>) => onStateChange({ ...state, ...patch });

  return (
    <div className="stack">
      <div className="card" style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
        <input value={state.result} onChange={(e) => set({ result: e.target.value })} placeholder="result" />
        <input value={state.compliance} onChange={(e) => set({ compliance: e.target.value })} placeholder="compliance" />
        <input value={state.complianceMin} onChange={(e) => set({ complianceMin: e.target.value })} placeholder="compliance min 0..1" />
        <input value={state.lineId} onChange={(e) => set({ lineId: e.target.value })} placeholder="line id" />
        <input value={state.player} onChange={(e) => set({ player: e.target.value })} placeholder="player" />
      </div>
      <table className="table"><tbody>{data?.map((game) => <tr key={game.id}><td>{game.id}</td><td><Link href={`/games/${game.id}`}>Open</Link></td></tr>)}</tbody></table>
    </div>
  );
}
