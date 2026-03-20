"use client";

import { Suspense, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { PageContainer, PageSection } from "@/components/app-shell";
import { DEFAULT_GAMES_TABLE_STATE, GamesTable, type GamesTableState } from "@/components/games/games-table";
import { SectionHeader } from "@/components/ui/section-header";

function parseState(params: URLSearchParams): GamesTableState { return { ...DEFAULT_GAMES_TABLE_STATE, result: params.get("result") ?? "", compliance: params.get("compliance") ?? "", complianceMin: params.get("compliance_min") ?? "", lineId: params.get("line_id") ?? "", player: params.get("player") ?? "", dateFrom: params.get("date_from") ?? "", dateTo: params.get("date_to") ?? "", sortBy: (params.get("sort_by") as GamesTableState["sortBy"]) || DEFAULT_GAMES_TABLE_STATE.sortBy, sortDir: (params.get("sort_dir") as GamesTableState["sortDir"]) || DEFAULT_GAMES_TABLE_STATE.sortDir }; }

function GamesPageContent() {
  const params = useSearchParams(); const router = useRouter(); const pathname = usePathname(); const state = useMemo(() => parseState(new URLSearchParams(params.toString())), [params]);
  function onStateChange(next: GamesTableState) { const nextParams = new URLSearchParams(); Object.entries(next).forEach(([key, value]) => { if (value) nextParams.set(key.replace(/[A-Z]/g, (m) => `_${m.toLowerCase()}`), value); }); router.replace(`${pathname}?${nextParams.toString()}`); }
  return <PageContainer title="Games" description="Filter recent games, review outcomes, and jump into detailed move inspection."><PageSection><SectionHeader title="Games" description="Filter and open recent games." /><GamesTable state={state} onStateChange={onStateChange} /></PageSection></PageContainer>;
}

export default function GamesPage() { return <Suspense fallback={<p className="text-sm text-text-muted">Loading games…</p>}><GamesPageContent /></Suspense>; }
