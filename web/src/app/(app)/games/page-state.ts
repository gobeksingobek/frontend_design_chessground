import { applyStoredGamesTableState, DEFAULT_GAMES_TABLE_STATE, type GamesTableState } from "@/components/games/games-table";

export function parseGamesPageState(params: URLSearchParams): GamesTableState {
  return applyStoredGamesTableState({
    result: params.get("result") ?? "",
    compliance: params.get("compliance") ?? "",
    complianceMin: params.get("compliance_min") ?? "",
    lineId: params.get("line_id") ?? "",
    player: params.get("player") ?? "",
    dateFrom: params.get("date_from") ?? "",
    dateTo: params.get("date_to") ?? "",
    sortBy: (params.get("sort_by") as GamesTableState["sortBy"]) || DEFAULT_GAMES_TABLE_STATE.sortBy,
    sortDir: (params.get("sort_dir") as GamesTableState["sortDir"]) || DEFAULT_GAMES_TABLE_STATE.sortDir,
  });
}

export function buildGamesPageQueryParams(state: GamesTableState): URLSearchParams {
  const nextParams = new URLSearchParams();
  Object.entries(state).forEach(([key, value]) => {
    if (value) nextParams.set(key.replace(/[A-Z]/g, (match) => `_${match.toLowerCase()}`), value);
  });
  return nextParams;
}
