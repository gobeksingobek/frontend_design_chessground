"use client";

import { Suspense, useMemo } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { PageContainer, PageSection } from "@/components/app-shell";
import { DEFAULT_GAMES_TABLE_STATE, GamesTable, type GamesTableState } from "@/components/games/games-table";
import { Button } from "@/components/ui/button";
import { DetailPane } from "@/components/ui/page-patterns";
import { SectionHeader } from "@/components/ui/section-header";
import { CaptionText, CardTitle, MutedText } from "@/components/ui/typography";

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

function GamesPageContent() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const state = useMemo(() => parseState(new URLSearchParams(params.toString())), [params]);

  function onStateChange(next: GamesTableState) {
    const nextParams = new URLSearchParams();
    Object.entries(next).forEach(([key, value]) => {
      if (value) nextParams.set(key.replace(/[A-Z]/g, (match) => `_${match.toLowerCase()}`), value);
    });
    router.replace(`${pathname}?${nextParams.toString()}`);
  }

  const activeFilterEntries = [
    ["Result", state.result],
    ["Compliance", state.compliance],
    ["Minimum compliance", state.complianceMin],
    ["Line", state.lineId],
    ["Player", state.player],
    ["Date range", state.dateFrom || state.dateTo ? `${state.dateFrom || "…"} → ${state.dateTo || "…"}` : ""],
  ].filter(([, value]) => Boolean(value));

  return (
    <PageContainer title="Games" description="Filter recent games, separate table context from selection context, and jump into move-level review.">
      <PageSection>
        <SectionHeader
          title="Game review workspace"
          description="Filters, table results, and selection guidance are separated into their own panels so the page is easier to scan."
          actions={<Link href="/analysis"><Button variant="ghost">Open board analysis</Button></Link>}
        />

        <div className="grid gap-grid-gap xl:grid-cols-[minmax(0,1.65fr)_minmax(300px,0.9fr)] xl:items-start">
          <GamesTable state={state} onStateChange={onStateChange} />

          <div className="grid gap-grid-gap xl:sticky xl:top-24">
            <DetailPane title="Selected context" description="Use this panel as a quick reminder of what the current table view is optimized to show.">
              <div className="grid gap-4">
                <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
                  <CaptionText>Active filters</CaptionText>
                  {activeFilterEntries.length === 0 ? <MutedText className="mt-2">No filters applied. You are viewing the broadest recent game list.</MutedText> : <ul className="mt-2 grid gap-2">{activeFilterEntries.map(([label, value]) => <li key={String(label)} className="text-sm text-foreground"><span className="font-medium">{label}:</span> {String(value)}</li>)}</ul>}
                </div>
                <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
                  <CaptionText>Current sort</CaptionText>
                  <CardTitle className="mt-2 text-base">{state.sortBy} · {state.sortDir}</CardTitle>
                  <MutedText className="mt-2">Sorting stays independent from the filter panel so you can change scanning order without resetting the query.</MutedText>
                </div>
                <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
                  <CaptionText>Next step</CaptionText>
                  <MutedText className="mt-2">Open a row from the table to review metadata, board state, and move quality in the redesigned game detail layout.</MutedText>
                </div>
              </div>
            </DetailPane>
          </div>
        </div>
      </PageSection>
    </PageContainer>
  );
}

export default function GamesPage() {
  return <Suspense fallback={<p className="text-sm text-text-muted">Loading games…</p>}><GamesPageContent /></Suspense>;
}
