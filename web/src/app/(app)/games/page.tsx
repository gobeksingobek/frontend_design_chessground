"use client";

import { Suspense, useMemo } from "react";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { buildGamesPageQueryParams, parseGamesPageState } from "./page-state";
import { PageContainer, PageSection } from "@/components/app-shell";
import { GamesTable, type GamesTableState } from "@/components/games/games-table";
import { Button } from "@/components/ui/button";
import { DetailPane } from "@/components/ui/page-patterns";
import { SectionHeader } from "@/components/ui/section-header";
import { CaptionText, CardTitle, MutedText } from "@/components/ui/typography";

function GamesPageContent() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const state = useMemo(() => parseGamesPageState(new URLSearchParams(params.toString())), [params]);

  function onStateChange(next: GamesTableState) {
    const nextParams = buildGamesPageQueryParams(next);
    const query = nextParams.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
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
  return <Suspense fallback={<div className="min-h-64" aria-busy="true" aria-label="Loading games" />}><GamesPageContent /></Suspense>;
}
