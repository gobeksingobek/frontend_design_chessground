"use client";

import { useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { DEFAULT_GAMES_TABLE_STATE, GamesTable, type GamesTableState } from "@/components/games/games-table";

function parseState(params: URLSearchParams): GamesTableState {
  return {
    ...DEFAULT_GAMES_TABLE_STATE,
    result: params.get("result") ?? "",
    compliance: params.get("compliance") ?? "",
    complianceMin: params.get("compliance_min") ?? "",
    lineId: params.get("line_id") ?? "",
    player: params.get("player") ?? "",
    dateFrom: params.get("date_from") ?? "",
    dateTo: params.get("date_to") ?? "",
    sortBy: (params.get("sort_by") as GamesTableState["sortBy"]) || DEFAULT_GAMES_TABLE_STATE.sortBy,
    sortDir: (params.get("sort_dir") as GamesTableState["sortDir"]) || DEFAULT_GAMES_TABLE_STATE.sortDir,
  };
}

export default function GamesPage() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const state = useMemo(() => parseState(new URLSearchParams(params.toString())), [params]);

  function onStateChange(next: GamesTableState) {
    const nextParams = new URLSearchParams();
    Object.entries(next).forEach(([key, value]) => {
      if (value) nextParams.set(key.replace(/[A-Z]/g, (m) => `_${m.toLowerCase()}`), value);
    });
    router.replace(`${pathname}?${nextParams.toString()}`);
  }

  return (
    <div className="stack">
      <h2>Games</h2>
      <GamesTable state={state} onStateChange={onStateChange} />
    </div>
  );
}
