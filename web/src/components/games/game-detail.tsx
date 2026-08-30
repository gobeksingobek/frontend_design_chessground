"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";

import { SidelineAnalysisForm } from "@/components/analysis/sideline-analysis-form";
import { ChessBoard } from "@/components/chess/chess-board";
import { EvalBar } from "@/components/games/eval-bar";
import { MoveQualityBadge } from "@/components/games/move-quality-badge";
import { DenseControlRow, DetailPane, EmptyState, FilterPanel } from "@/components/ui/page-patterns";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableContainer, TableHead, Td, Th } from "@/components/ui/table";
import { BodyText, CaptionText, CardTitle, FieldLabel, MutedText } from "@/components/ui/typography";
import { cn } from "@/lib/cn";
import { getGame } from "@/lib/api-client";

export function applyCursorKey(key: string, current: number, max: number): number { if (key === "ArrowRight") return Math.min(max, current + 1); if (key === "ArrowLeft") return Math.max(0, current - 1); if (key === "ArrowUp" || key === "End") return max; if (key === "ArrowDown" || key === "Home") return 0; return current; }
export function isCursorNavigationKey(key: string): boolean { return key === "ArrowRight" || key === "ArrowLeft" || key === "ArrowUp" || key === "ArrowDown" || key === "Home" || key === "End"; }
export function resolveCursorIndexForPly(moves: Array<{ ply: number }>, selectedPly: number | null, fallbackCursor: number): number {
  if (!moves.length) return 0;
  if (selectedPly !== null) {
    const nextIndex = moves.findIndex((move) => move.ply === selectedPly);
    if (nextIndex >= 0) return nextIndex + 1;
  }
  return Math.min(Math.max(fallbackCursor, 0), moves.length);
}
function shouldIgnoreKeyboardEvent(event: KeyboardEvent | ReactKeyboardEvent): boolean { const target = event.target; if (!(target instanceof HTMLElement)) return false; const tagName = target.tagName; if (tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT") return true; return target.isContentEditable; }
function metadataEntries(header: Record<string, unknown> | null | undefined) { if (!header) return []; return Object.entries(header).filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== ""); }
export function buildGameRouteQuery(selectedPly: number | null, activeTab: "board" | "moves", orientation: "white" | "black") {
  return {
    ...(selectedPly ? { ply: String(selectedPly) } : {}),
    tab: activeTab,
    orientation,
  };
}
export function buildTreePositionRouteQuery(posId: number) {
  return { pos_id: String(posId || 1) };
}
function buildGameHref(gameId: number, selectedPly: number | null, activeTab: "board" | "moves", orientation: "white" | "black") {
  const params = new URLSearchParams(buildGameRouteQuery(selectedPly, activeTab, orientation));
  return `/games/${gameId}?${params.toString()}`;
}

export function GameDetail({
  gameId,
  initialPly,
  initialTab,
  initialOrientation,
}: {
  gameId: number;
  initialPly: number | null;
  initialTab: "board" | "moves";
  initialOrientation: "white" | "black";
}) {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const initializedGameIdRef = useRef<number | null>(null);
  const selectedPlyRef = useRef<number | null>(null);
  const shouldRestoreContainerFocusRef = useRef(false);
  const [cursorIndex, setCursorIndex] = useState(0);
  const [activeTab, setActiveTab] = useState<"board" | "moves">(initialTab);
  const [orientation, setOrientation] = useState<"white" | "black">(initialOrientation);
  const { data, isLoading, error } = useQuery({ queryKey: ["game", gameId], queryFn: () => getGame(gameId) });
  const moves = useMemo(() => data?.moves ?? [], [data]);
  const headerEntries = useMemo(() => metadataEntries(data?.header), [data?.header]);

  useEffect(() => {
    if (!moves.length) {
      setCursorIndex(0);
      selectedPlyRef.current = null;
      return;
    }
    if (initializedGameIdRef.current !== gameId) {
      initializedGameIdRef.current = gameId;
      const initialCursor = resolveCursorIndexForPly(moves, initialPly, 0);
      setCursorIndex(initialCursor);
      selectedPlyRef.current = initialCursor > 0 ? moves[initialCursor - 1]?.ply ?? null : null;
      return;
    }
    setCursorIndex((current) => {
      const nextCursor = resolveCursorIndexForPly(moves, selectedPlyRef.current, current);
      selectedPlyRef.current = nextCursor > 0 ? moves[nextCursor - 1]?.ply ?? null : null;
      return nextCursor;
    });
  }, [gameId, initialPly, moves]);

  const selectedMove = useMemo(() => (cursorIndex === 0 ? null : moves[cursorIndex - 1] ?? null), [moves, cursorIndex]);
  const selectedPly = selectedMove?.ply ?? null;
  const boardFen = useMemo(() => (!moves.length || cursorIndex === 0 ? undefined : selectedMove?.fen ?? undefined), [moves.length, cursorIndex, selectedMove]);
  const lastMove = useMemo(() => {
    if (!selectedMove?.uci_move || selectedMove.uci_move.length < 4) return null;
    return { from: selectedMove.uci_move.slice(0, 2), to: selectedMove.uci_move.slice(2, 4) };
  }, [selectedMove]);
  const hasEvalData = selectedMove?.pre_eval_cp !== null || selectedMove?.post_eval_cp !== null;
  const navigateNext = useCallback(() => { setCursorIndex((current) => Math.min(moves.length, current + 1)); }, [moves.length]);
  const navigatePrev = useCallback(() => { setCursorIndex((current) => Math.max(0, current - 1)); }, []);
  const navigateStart = useCallback(() => { setCursorIndex(0); }, []);
  const navigateEnd = useCallback(() => { setCursorIndex(moves.length); }, [moves.length]);
  useEffect(() => {
    if (!moves.length || cursorIndex === 0) {
      selectedPlyRef.current = null;
      return;
    }
    selectedPlyRef.current = moves[cursorIndex - 1]?.ply ?? null;
  }, [cursorIndex, moves]);

  useEffect(() => {
    if (!shouldRestoreContainerFocusRef.current) return;
    shouldRestoreContainerFocusRef.current = false;
    containerRef.current?.focus();
  }, [cursorIndex]);

  const nav = data?.navigation;
  const prevGameId = nav?.prev_game_id ?? data?.prev_game_id ?? null;
  const nextGameId = nav?.next_game_id ?? data?.next_game_id ?? null;

  const onKeyNavigate = useCallback((event: KeyboardEvent | ReactKeyboardEvent) => {
    if (shouldIgnoreKeyboardEvent(event)) return;
    if (event.altKey && prevGameId && event.key === "ArrowLeft") {
      event.preventDefault();
      router.push(buildGameHref(prevGameId, selectedPly, activeTab, orientation));
      return;
    }
    if (event.altKey && nextGameId && event.key === "ArrowRight") {
      event.preventDefault();
      router.push(buildGameHref(nextGameId, selectedPly, activeTab, orientation));
      return;
    }
    const nextCursor = applyCursorKey(event.key, cursorIndex, moves.length);
    if (nextCursor !== cursorIndex) {
      event.preventDefault();
      if (typeof document !== "undefined" && document.activeElement === containerRef.current) {
        shouldRestoreContainerFocusRef.current = true;
      }
      setCursorIndex(nextCursor);
    }
  }, [activeTab, cursorIndex, moves.length, nextGameId, orientation, prevGameId, router, selectedPly]);

  if (isLoading) return <MutedText>Loading game detail...</MutedText>;
  if (error) return <BodyText className="font-medium text-danger">Failed to load game detail: {(error as Error).message}</BodyText>;

  return (
    <div className="grid gap-section-gap" onKeyDown={onKeyNavigate} tabIndex={0} ref={containerRef}>
      <DetailPane title="Game summary" description="Metadata is grouped into a readable summary card so you can orient yourself before stepping through the board and move list.">
        <div className="flex flex-wrap items-center justify-between gap-control-gap">
          <div className="grid gap-xs">
            <CaptionText>Game detail</CaptionText>
            <CardTitle>Game #{gameId}</CardTitle>
            <MutedText>Use the move table or keyboard shortcuts to step through the position history.</MutedText>
          </div>
          <DenseControlRow>
            <Select value={activeTab} onChange={(event) => setActiveTab(event.target.value === "moves" ? "moves" : "board")}>
              <option value="board">Board tab</option>
              <option value="moves">Moves tab</option>
            </Select>
            <Select value={orientation} onChange={(event) => setOrientation(event.target.value === "black" ? "black" : "white")}>
              <option value="white">White orientation</option>
              <option value="black">Black orientation</option>
            </Select>
            {prevGameId ? <Link className="text-label font-medium text-primary hover:text-secondary" href={{ pathname: `/games/${prevGameId}`, query: buildGameRouteQuery(selectedPly, activeTab, orientation) }} title={data?.prev_game_label ?? undefined}>← Previous game</Link> : <span className="text-label text-muted-foreground/70">← Previous game</span>}
            {nextGameId ? <Link className="text-label font-medium text-primary hover:text-secondary" href={{ pathname: `/games/${nextGameId}`, query: buildGameRouteQuery(selectedPly, activeTab, orientation) }} title={data?.next_game_label ?? undefined}>Next game →</Link> : <span className="text-label text-muted-foreground/70">Next game →</span>}
          </DenseControlRow>
        </div>
        {headerEntries.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {headerEntries.map(([label, value]) => (
              <div key={label} className="rounded-xl border border-border/70 bg-card px-4 py-4">
                <FieldLabel as="span">{label}</FieldLabel>
                <BodyText className="mt-2 break-words leading-6">{String(value)}</BodyText>
              </div>
            ))}
          </div>
        ) : <EmptyState title="No game metadata" description="This game does not currently expose header fields." />}
      </DetailPane>

      <div className={cn("grid gap-grid-gap xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)] xl:items-start", activeTab === "moves" && "xl:grid-cols-1")}>
        <DetailPane title="Board review" description="The board and move-level analysis stay side by side so board navigation never competes with the selected context.">
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.95fr)] xl:items-start">
            <ChessBoard fen={boardFen} title="Selected game position" subtitle="Board highlights stay in sync with the selected move, analysis tools, and keyboard navigation." currentPlyIndex={cursorIndex} lastMove={lastMove} onNavigateNext={navigateNext} onNavigatePrev={navigatePrev} onNavigateStart={navigateStart} onNavigateEnd={navigateEnd} onMoveAttempt={({ uci }) => { const nextMove = moves[cursorIndex]; if (nextMove?.uci_move === uci) navigateNext(); }} size="large" orientation={orientation} />
            <div className="grid gap-4 xl:sticky xl:top-24">
              <FilterPanel title="Analysis side panel" description="Selection controls, eval summaries, and sideline actions stay together next to the board.">
                <label className="grid gap-xs">
                  <FieldLabel as="span">Move ply</FieldLabel>
                  <Select value={selectedPly ?? ""} onChange={(event) => { const ply = event.target.value ? Number(event.target.value) : null; if (ply === null) { setCursorIndex(0); return; } const moveIndex = moves.findIndex((move) => move.ply === ply); setCursorIndex(moveIndex >= 0 ? moveIndex + 1 : 0); }}>
                    <option value="">Initial position</option>
                    {moves.map((move) => <option key={move.ply} value={move.ply}>Ply {move.ply} - {move.san_move ?? move.uci_move ?? "-"}</option>)}
                  </Select>
                </label>
                {selectedMove ? (
                  <div className="grid gap-3">
                    <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
                      <CaptionText>Selected move</CaptionText>
                      <CardTitle className="mt-2 text-base">Ply {selectedMove.ply}: {selectedMove.san_move ?? selectedMove.uci_move ?? "-"}</CardTitle>
                    </div>
                    <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
                      <CaptionText>Classification</CaptionText>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <MoveQualityBadge label={selectedMove.quality_label} />
                        <span className="text-sm text-muted-foreground">{selectedMove.repertoire_class ?? "No repertoire class"}</span>
                      </div>
                    </div>
                    <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
                      <CaptionText>Your CPL</CaptionText>
                      <CardTitle className={cn("mt-2 text-base", selectedMove.your_cpl !== null && selectedMove.your_cpl > 120 ? "text-danger" : "text-success")}>{selectedMove.your_cpl ?? "—"}</CardTitle>
                    </div>
                  </div>
                ) : <MutedText>Select a move to populate the analysis side panel.</MutedText>}
              </FilterPanel>
              {selectedMove ? (
                hasEvalData ? <div className="grid gap-4 xl:grid-cols-1"><EvalBar evalCp={selectedMove.pre_eval_cp} title="Before move" /><EvalBar evalCp={selectedMove.post_eval_cp} title="After move" /></div> : <DetailPane title="Eval panel" description="No pre/post eval values are available for the selected move."><MutedText>Evaluation data will appear here when engine scores are available.</MutedText></DetailPane>
              ) : null}
              {selectedMove?.fen ? <BodyText className="rounded-xl border border-border/70 bg-background/60 px-4 py-3"><Link className="font-medium text-primary hover:text-secondary" href={{ pathname: "/analysis", query: { game_id: String(gameId), move_ply: String(selectedMove.ply), fen: selectedMove.fen } }}>Open in /analysis with this position</Link></BodyText> : null}
              {selectedMove ? <BodyText className="rounded-xl border border-border/70 bg-background/60 px-4 py-3"><Link className="font-medium text-primary hover:text-secondary" href={{ pathname: "/tree", query: buildTreePositionRouteQuery(selectedMove.pos_id) }}>Open position #{selectedMove.pos_id} in tree intelligence</Link></BodyText> : null}
              {selectedMove?.fen ? <SidelineAnalysisForm key={`${selectedMove.ply}-${selectedMove.fen}`} title="Queue sideline from this game move" initialGameId={String(gameId)} initialMovePly={selectedMove.ply} initialFen={selectedMove.fen} lockedFields={{ gameId: true, movePly: true, fen: true }} /> : <EmptyState title="Select a move to analyze" description="Choose a move with an available FEN to queue a quick sideline evaluation from this game." />}
            </div>
          </div>
        </DetailPane>

        <DetailPane title="Review guidance" description="Keep the selected context separate from the move list so the row table can stay dense and readable.">
          <div className="grid gap-4">
            <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
              <CaptionText>Keyboard navigation</CaptionText>
              <MutedText className="mt-2">Use ← and → to move one ply at a time, Home to reset to the start, and End to jump to the latest move.</MutedText>
            </div>
            <div className="rounded-xl border border-border/70 bg-card px-4 py-4">
              <CaptionText>Table emphasis</CaptionText>
              <MutedText className="mt-2">The selected move row is highlighted so it remains visually tied to the board and side panel while you scroll.</MutedText>
            </div>
          </div>
        </DetailPane>
      </div>

      <DetailPane title="Move list" description="Rows are styled for stronger emphasis, and the header stays sticky while you scroll longer games.">
        {moves.length === 0 ? <EmptyState title="No moves recorded" description="This game does not have move data available yet." /> : (
          <TableContainer className="max-h-[42rem] overflow-auto">
            <Table>
              <TableHead className="sticky top-0 z-10 bg-elevated/95 backdrop-blur">
                <tr><Th>Ply</Th><Th>SAN</Th><Th>UCI</Th><Th>Class</Th><Th>Quality</Th><Th>Your CPL</Th><Th>Position</Th></tr>
              </TableHead>
              <TableBody>
                {moves.map((move) => (
                  <tr key={move.ply} className={cn("cursor-pointer border-b border-border/50 transition hover:bg-hover", move.ply === selectedPly && "bg-selection shadow-soft")} onClick={() => { const moveIndex = moves.findIndex((candidate) => candidate.ply === move.ply); setCursorIndex(moveIndex + 1); }}>
                    <Td className={move.ply === selectedPly ? "text-selection-foreground font-semibold" : undefined}>{move.ply}</Td>
                    <Td className={move.ply === selectedPly ? "text-selection-foreground font-semibold" : "font-medium"}>{move.san_move ?? "-"}</Td>
                    <Td className={cn(move.ply === selectedPly ? "text-selection-foreground" : undefined, "font-mono text-mono")}>{move.uci_move ?? "-"}</Td>
                    <Td className={move.ply === selectedPly ? "text-selection-foreground" : undefined}>{move.repertoire_class ?? "-"}</Td>
                    <Td><MoveQualityBadge label={move.quality_label} /></Td>
                    <Td className={cn(move.ply === selectedPly && "text-selection-foreground", move.your_cpl !== null && move.your_cpl > 120 ? "text-danger" : "text-success", "font-medium")}>{move.your_cpl ?? "-"}</Td>
                    <Td><Link className="font-medium text-primary hover:text-secondary" href={{ pathname: "/tree", query: buildTreePositionRouteQuery(move.pos_id) }}>#{move.pos_id}</Link></Td>
                  </tr>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DetailPane>
    </div>
  );
}
