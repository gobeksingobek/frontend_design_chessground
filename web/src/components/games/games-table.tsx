"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { listGamesFiltered } from "@/lib/api-client";

const STORAGE_KEY = "cg_games_table_state_v1";

export interface GamesTableState {
  result: string;
  compliance: string;
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
  return [
    "games",
    state.result,
    state.compliance,
    state.lineId,
    state.player,
    state.dateFrom,
    state.dateTo,
    state.sortBy,
    state.sortDir,
  ];
}

export function GamesTable() {
  const [state, setState] = useState<GamesTableState>(DEFAULT_GAMES_TABLE_STATE);

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as Partial<GamesTableState>;
      setState(applyStoredGamesTableState(parsed));
    } catch {
      setState(DEFAULT_GAMES_TABLE_STATE);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const queryKey = useMemo(() => buildGamesQueryKey(state), [state]);

  const { data, isLoading, error } = useQuery({
    queryKey,
    queryFn: () =>
      listGamesFiltered({
        limit: 200,
        offset: 0,
        result: state.result || undefined,
        compliance: state.compliance || undefined,
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

  return (
    <div className="stack">
      <div className="card" style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
        <label>
          Result
          <input value={state.result} onChange={(e) => setState((prev) => ({ ...prev, result: e.target.value }))} placeholder="1-0 / 0-1 / 1/2-1/2" />
        </label>
        <label>
          Compliance
          <input value={state.compliance} onChange={(e) => setState((prev) => ({ ...prev, compliance: e.target.value }))} placeholder="FULLY_COMPLIANT" />
        </label>
        <label>
          Line
          <input value={state.lineId} onChange={(e) => setState((prev) => ({ ...prev, lineId: e.target.value }))} placeholder="line id" />
        </label>
        <label>
          Player
          <input value={state.player} onChange={(e) => setState((prev) => ({ ...prev, player: e.target.value }))} placeholder="name contains" />
        </label>
        <label>
          Date from
          <input value={state.dateFrom} onChange={(e) => setState((prev) => ({ ...prev, dateFrom: e.target.value }))} placeholder="YYYY.MM.DD" />
        </label>
        <label>
          Date to
          <input value={state.dateTo} onChange={(e) => setState((prev) => ({ ...prev, dateTo: e.target.value }))} placeholder="YYYY.MM.DD" />
        </label>
        <label>
          Sort by
          <select value={state.sortBy} onChange={(e) => setState((prev) => ({ ...prev, sortBy: e.target.value as GamesTableState["sortBy"] }))}>
            <option value="date">date</option>
            <option value="result">result</option>
            <option value="compliance">compliance</option>
            <option value="id">id</option>
          </select>
        </label>
        <label>
          Direction
          <select value={state.sortDir} onChange={(e) => setState((prev) => ({ ...prev, sortDir: e.target.value as GamesTableState["sortDir"] }))}>
            <option value="desc">desc</option>
            <option value="asc">asc</option>
          </select>
        </label>
      </div>

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
    </div>
  );
}
