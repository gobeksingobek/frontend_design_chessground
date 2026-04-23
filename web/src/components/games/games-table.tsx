"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { DenseControlRow, DetailPane, EmptyState, FilterPanel } from "@/components/ui/page-patterns";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableContainer, TableHead, TableRow, Td, Th } from "@/components/ui/table";
import { CaptionText, MutedText } from "@/components/ui/typography";
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

export const DEFAULT_GAMES_TABLE_STATE: GamesTableState = { result: "", compliance: "", complianceMin: "", lineId: "", player: "", dateFrom: "", dateTo: "", sortBy: "date", sortDir: "desc" };
export function applyStoredGamesTableState(parsed: Partial<GamesTableState>): GamesTableState {
  const sortBy = parsed.sortBy && ["date", "result", "compliance", "id"].includes(parsed.sortBy) ? parsed.sortBy : DEFAULT_GAMES_TABLE_STATE.sortBy;
  const sortDir = parsed.sortDir && ["asc", "desc"].includes(parsed.sortDir) ? parsed.sortDir : DEFAULT_GAMES_TABLE_STATE.sortDir;
  return { ...DEFAULT_GAMES_TABLE_STATE, ...parsed, sortBy, sortDir };
}
export function buildGamesQueryKey(state: GamesTableState): string[] { return ["games", ...Object.values(state)]; }

export function GamesTable({ state, onStateChange }: { state: GamesTableState; onStateChange: (next: GamesTableState) => void }) {
  const queryKey = useMemo(() => buildGamesQueryKey(state), [state]);
  const { data, isLoading, error } = useQuery({
    queryKey,
    queryFn: () => listGamesFiltered({
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

  const set = (patch: Partial<GamesTableState>) => onStateChange({ ...state, ...patch });
  const clearFilters = () => onStateChange(DEFAULT_GAMES_TABLE_STATE);

  return (
    <div className="grid gap-grid-gap">
      <FilterPanel title="Filters" description="Tighten the search criteria first, then use the separate results panel to scan games without visual overlap.">
        <div className="grid gap-grid-gap xl:grid-cols-[minmax(0,1.25fr)_minmax(260px,0.75fr)]">
          <div className="grid gap-control-gap md:grid-cols-2 xl:grid-cols-4">
            <FormField label="Result" helpText="Filter by result such as 1-0, 0-1, or 1/2-1/2."><Input value={state.result} onChange={(e) => set({ result: e.target.value })} placeholder="1-0" /></FormField>
            <FormField label="Compliance" helpText="Match a backend compliance bucket or label."><Input value={state.compliance} onChange={(e) => set({ compliance: e.target.value })} placeholder="in_book" /></FormField>
            <FormField label="Minimum compliance" helpText="Use a decimal from 0 to 1."><Input value={state.complianceMin} onChange={(e) => set({ complianceMin: e.target.value })} placeholder="0.75" inputMode="decimal" /></FormField>
            <FormField label="Line ID" helpText="Limit results to a single repertoire line."><Input value={state.lineId} onChange={(e) => set({ lineId: e.target.value })} placeholder="sicilian-main" /></FormField>
            <FormField label="Player" helpText="Matches either white or black player names."><Input value={state.player} onChange={(e) => set({ player: e.target.value })} placeholder="Carlsen" /></FormField>
            <FormField label="Date from" helpText="Start date for the search window."><Input type="date" value={state.dateFrom} onChange={(e) => set({ dateFrom: e.target.value })} /></FormField>
            <FormField label="Date to" helpText="End date for the search window."><Input type="date" value={state.dateTo} onChange={(e) => set({ dateTo: e.target.value })} /></FormField>
          </div>

          <div className="grid gap-4 rounded-xl border border-border/70 bg-card px-4 py-4">
            <div>
              <CaptionText>Table controls</CaptionText>
              <MutedText className="mt-2">Sorting and reset actions stay separate from field filters so the table behavior is easier to understand.</MutedText>
            </div>
            <FormField label="Sort by" helpText="Choose the primary column used to order rows.">
              <Select value={state.sortBy} onChange={(e) => set({ sortBy: e.target.value as GamesTableState["sortBy"] })}>
                <option value="date">Date</option>
                <option value="result">Result</option>
                <option value="compliance">Compliance</option>
                <option value="id">Game ID</option>
              </Select>
            </FormField>
            <FormField label="Direction" helpText="Reverse the current sort order.">
              <Select value={state.sortDir} onChange={(e) => set({ sortDir: e.target.value as GamesTableState["sortDir"] })}>
                <option value="desc">Descending</option>
                <option value="asc">Ascending</option>
              </Select>
            </FormField>
            <DenseControlRow>
              <Button variant="ghost" onClick={clearFilters}>Reset all</Button>
            </DenseControlRow>
          </div>
        </div>
      </FilterPanel>

      <DetailPane title="Results table" description="The game list is isolated from filters so row scanning and selected actions remain visually distinct.">
        {error ? <p className="text-sm text-danger">Failed to load games: {(error as Error).message}</p> : null}
        {isLoading ? <GamesTableLoading /> : null}
        {!isLoading && !error && (data?.length ?? 0) === 0 ? <EmptyState title="No games match these filters" description="Adjust the result, player, line, or compliance filters to broaden the list." /> : null}
        {!isLoading && !error && (data?.length ?? 0) > 0 ? (
          <TableContainer>
            <Table>
              <TableHead>
                <tr>
                  <Th>ID</Th><Th>Date</Th><Th>Players</Th><Th>Result</Th><Th>Line</Th><Th>Compliance</Th><Th>Matched ply</Th><Th className="text-right">Action</Th>
                </tr>
              </TableHead>
              <TableBody>
                {data?.map((game) => (
                  <TableRow key={game.id} className="hover:bg-hover">
                    <Td className="font-medium">{game.id}</Td>
                    <Td>{game.date ?? "—"}</Td>
                    <Td>
                      <div className="grid gap-1 leading-6">
                        <span>{game.white ?? "Unknown white"}</span>
                        <span className="text-sm text-muted-foreground">vs {game.black ?? "Unknown black"}</span>
                      </div>
                    </Td>
                    <Td>{game.result ?? "—"}</Td>
                    <Td className="max-w-[12rem] truncate">{game.line_id ?? "—"}</Td>
                    <Td>{game.compliance ?? "—"}</Td>
                    <Td>{game.max_matched_ply ?? "—"}</Td>
                    <Td className="text-right"><Link href={`/games/${game.id}`}><Button variant="ghost" size="sm">Open</Button></Link></Td>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        ) : null}
      </DetailPane>
    </div>
  );
}

function GamesTableLoading() {
  return (
    <TableContainer>
      <Table>
        <TableHead><tr><Th>ID</Th><Th>Date</Th><Th>Players</Th><Th>Result</Th><Th>Line</Th><Th>Compliance</Th><Th>Matched ply</Th><Th>Action</Th></tr></TableHead>
        <TableBody>
          {Array.from({ length: 5 }).map((_, index) => (
            <TableRow key={index}>
              {Array.from({ length: 8 }).map((__, cell) => <Td key={cell}><Skeleton className="h-5 w-full min-w-16" /></Td>)}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
