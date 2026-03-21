"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";

import { SidelineAnalysisForm } from "@/components/analysis/sideline-analysis-form";
import { ChessBoard } from "@/components/chess/chess-board";
import { EvalBar } from "@/components/games/eval-bar";
import { MoveQualityBadge } from "@/components/games/move-quality-badge";
import { DenseControlRow, DetailPane, EmptyState, FilterPanel } from "@/components/ui/page-patterns";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableHead, Td, Th } from "@/components/ui/table";
import { BodyText, CaptionText, CardTitle, FieldLabel, MonoText, MutedText } from "@/components/ui/typography";
import { cn } from "@/lib/cn";
import { getGame } from "@/lib/api-client";

export function applyCursorKey(key: string, current: number, max: number): number { if (key === "ArrowRight") return Math.min(max, current + 1); if (key === "ArrowLeft") return Math.max(0, current - 1); if (key === "ArrowUp" || key === "End") return max; if (key === "ArrowDown" || key === "Home") return 0; return current; }
function shouldIgnoreKeyboardEvent(event: KeyboardEvent | ReactKeyboardEvent): boolean { const target = event.target; if (!(target instanceof HTMLElement)) return false; const tagName = target.tagName; if (tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT") return true; return target.isContentEditable; }
function metadataEntries(header: Record<string, unknown> | null | undefined) { if (!header) return []; return Object.entries(header).filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== ""); }

export function GameDetail({ gameId, initialPly }: { gameId: number; initialPly: number | null }) {
  const [cursorIndex, setCursorIndex] = useState(0);
  const { data, isLoading, error } = useQuery({ queryKey: ["game", gameId], queryFn: () => getGame(gameId) });
  const moves = useMemo(() => data?.moves ?? [], [data]);
  const headerEntries = useMemo(() => metadataEntries(data?.header), [data?.header]);
  useEffect(() => { if (!moves.length) { setCursorIndex(0); return; } if (initialPly !== null) { const moveIndex = moves.findIndex((move) => move.ply === initialPly); if (moveIndex >= 0) { setCursorIndex(moveIndex + 1); return; } } setCursorIndex(0); }, [gameId, initialPly, moves]);
  const selectedMove = useMemo(() => (cursorIndex === 0 ? null : moves[cursorIndex - 1] ?? null), [moves, cursorIndex]);
  const selectedPly = selectedMove?.ply ?? null;
  const boardFen = useMemo(() => (!moves.length || cursorIndex === 0 ? undefined : selectedMove?.fen ?? undefined), [moves.length, cursorIndex, selectedMove]);
  const lastMove = useMemo(() => {
    if (!selectedMove?.uci_move || selectedMove.uci_move.length < 4) return null;
    return { from: selectedMove.uci_move.slice(0, 2), to: selectedMove.uci_move.slice(2, 4) };
  }, [selectedMove?.uci_move]);
  const hasEvalData = selectedMove?.pre_eval_cp !== null || selectedMove?.post_eval_cp !== null;
  const navigateNext = useCallback(() => { setCursorIndex((current) => Math.min(moves.length, current + 1)); }, [moves.length]);
  const navigatePrev = useCallback(() => { setCursorIndex((current) => Math.max(0, current - 1)); }, []);
  const navigateStart = useCallback(() => { setCursorIndex(0); }, []);
  const navigateEnd = useCallback(() => { setCursorIndex(moves.length); }, [moves.length]);
  const onKeyNavigate = useCallback((event: KeyboardEvent | ReactKeyboardEvent) => { if (shouldIgnoreKeyboardEvent(event)) return; const nextCursor = applyCursorKey(event.key, cursorIndex, moves.length); if (nextCursor !== cursorIndex) { event.preventDefault(); setCursorIndex(nextCursor); } }, [cursorIndex, moves.length]);
  if (isLoading) return <MutedText>Loading game detail...</MutedText>;
  if (error) return <BodyText className="font-medium text-danger">Failed to load game detail: {(error as Error).message}</BodyText>;

  return (
    <div className="grid gap-section-gap" onKeyDown={onKeyNavigate} tabIndex={0}>
      <DetailPane title="Game header" description="Navigate between adjacent games and review curated game metadata instead of raw header JSON.">
        <div className="flex flex-wrap items-center justify-between gap-control-gap">
          <div className="grid gap-xs">
            <CaptionText>Game detail</CaptionText>
            <CardTitle>Game #{gameId}</CardTitle>
            <MutedText>Use the move table or keyboard shortcuts to step through the position history.</MutedText>
          </div>
          <DenseControlRow>
            {data?.prev_game_id ? <Link className="text-label font-medium text-primary hover:text-secondary" href={{ pathname: `/games/${data.prev_game_id}`, query: selectedPly ? { ply: String(selectedPly) } : {} }}>← Previous game</Link> : <span className="text-label text-muted-foreground/70">← Previous game</span>}
            {data?.next_game_id ? <Link className="text-label font-medium text-primary hover:text-secondary" href={{ pathname: `/games/${data.next_game_id}`, query: selectedPly ? { ply: String(selectedPly) } : {} }}>Next game →</Link> : <span className="text-label text-muted-foreground/70">Next game →</span>}
          </DenseControlRow>
        </div>
        {headerEntries.length > 0 ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{headerEntries.map(([label, value]) => <div key={label} className="rounded-xl border border-border/70 bg-card px-4 py-4"><FieldLabel as="span">{label}</FieldLabel><BodyText className="mt-2 break-words leading-6">{String(value)}</BodyText></div>)}</div> : <EmptyState title="No game metadata" description="This game does not currently expose header fields." />}
      </DetailPane>

      <div className="grid gap-grid-gap xl:grid-cols-board">
        <DetailPane title="Selected position" description="Review the board state and queue sideline analysis from any move with a FEN." className="gap-5">
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.95fr)] xl:items-start">
            <ChessBoard fen={boardFen} title="Selected game position" subtitle="Board highlights stay in sync with the selected move, analysis tools, and keyboard navigation." currentPlyIndex={cursorIndex} lastMove={lastMove} onNavigateNext={navigateNext} onNavigatePrev={navigatePrev} onNavigateStart={navigateStart} onNavigateEnd={navigateEnd} onMoveAttempt={({ uci }) => { const nextMove = moves[cursorIndex]; if (nextMove?.uci_move === uci) navigateNext(); }} size="large" />
            <div className="grid gap-4 xl:sticky xl:top-24">
              <FilterPanel title="Move selector" description="Keep dense controls compact while the board and detail regions stay spacious.">
            <label className="grid max-w-md gap-xs">
              <FieldLabel as="span">Move ply</FieldLabel>
              <Select value={selectedPly ?? ""} onChange={(event) => { const ply = event.target.value ? Number(event.target.value) : null; if (ply === null) { setCursorIndex(0); return; } const moveIndex = moves.findIndex((move) => move.ply === ply); setCursorIndex(moveIndex >= 0 ? moveIndex + 1 : 0); }}><option value="">Initial position</option>{moves.map((move) => <option key={move.ply} value={move.ply}>Ply {move.ply} - {move.san_move ?? move.uci_move ?? "-"}</option>)}</Select>
            </label>
              </FilterPanel>
              {selectedMove?.fen ? <BodyText className="rounded-xl border border-border/70 bg-background/60 px-4 py-3"><Link className="font-medium text-primary hover:text-secondary" href={{ pathname: "/analysis", query: { game_id: String(gameId), move_ply: String(selectedMove.ply), fen: selectedMove.fen } }}>Open in /analysis with this position</Link></BodyText> : null}
              {selectedMove?.fen ? <SidelineAnalysisForm key={`${selectedMove.ply}-${selectedMove.fen}`} title="Queue sideline from this game move" initialGameId={String(gameId)} initialMovePly={selectedMove.ply} initialFen={selectedMove.fen} lockedFields={{ gameId: true, movePly: true, fen: true }} /> : <EmptyState title="Select a move to analyze" description="Choose a move with an available FEN to queue a quick sideline evaluation from this game." />}
            </div>
          </div>
        </DetailPane>

        <div className="grid gap-grid-gap">
          {selectedMove ? <div className="grid gap-grid-gap xl:grid-cols-3"><DetailPane title="Selected ply details"><div className="grid gap-4"><div className="grid gap-1"><FieldLabel as="span">Move</FieldLabel><CardTitle>Ply {selectedMove.ply}: {selectedMove.san_move ?? selectedMove.uci_move ?? "-"}</CardTitle></div><div className="grid gap-1"><FieldLabel as="span">Quality</FieldLabel><div><MoveQualityBadge label={selectedMove.quality_label} /></div></div><div className="grid gap-1"><FieldLabel as="span">Your CPL</FieldLabel><BodyText className={cn("font-medium", selectedMove.your_cpl !== null && selectedMove.your_cpl > 120 ? "text-danger" : "text-success")}>{selectedMove.your_cpl ?? "-"}</BodyText></div></div></DetailPane>{hasEvalData ? <><EvalBar evalCp={selectedMove.pre_eval_cp} title="Before move" /><EvalBar evalCp={selectedMove.post_eval_cp} title="After move" /></> : <DetailPane title="Eval panel" description="No pre/post eval values are available for the selected move."><MutedText>Evaluation data will appear here when pre/post engine scores are available.</MutedText></DetailPane>}</div> : <EmptyState title="No move selected" description="Select a move from the table to populate the detail pane and evaluation cards." />}
          {data?.header ? <DetailPane title="Developer diagnostics" description="Reserve monospaced formatting for payload inspection when troubleshooting header shape changes."><MonoText as="pre" className="overflow-x-auto rounded-lg border border-border bg-muted p-4">{JSON.stringify(data.header, null, 2)}</MonoText></DetailPane> : null}
        </div>
      </div>

      <DetailPane title="Moves" description="Click a row or use arrow keys while focused to step through the game.">
        {moves.length === 0 ? <EmptyState title="No moves recorded" description="This game does not have move data available yet." /> : <Table>
          <TableHead><tr><Th>Ply</Th><Th>SAN</Th><Th>UCI</Th><Th>Class</Th><Th>Quality</Th><Th>Your CPL</Th></tr></TableHead>
          <TableBody>{moves.map((move) => <tr key={move.ply} className={cn("cursor-pointer transition hover:bg-hover", move.ply === selectedPly && "bg-selection")} onClick={() => { const moveIndex = moves.findIndex((candidate) => candidate.ply === move.ply); setCursorIndex(moveIndex + 1); }}><Td className={move.ply === selectedPly ? "text-selection-foreground" : undefined}>{move.ply}</Td><Td className={move.ply === selectedPly ? "text-selection-foreground font-medium" : "font-medium"}>{move.san_move ?? "-"}</Td><Td className={cn(move.ply === selectedPly ? "text-selection-foreground" : undefined, "font-mono text-mono")}>{move.uci_move ?? "-"}</Td><Td className={move.ply === selectedPly ? "text-selection-foreground" : undefined}>{move.repertoire_class ?? "-"}</Td><Td><MoveQualityBadge label={move.quality_label} /></Td><Td className={cn(move.ply === selectedPly && "text-selection-foreground", move.your_cpl !== null && move.your_cpl > 120 ? "text-danger" : "text-success", "font-medium")}>{move.your_cpl ?? "-"}</Td></tr>)}</TableBody>
        </Table>}
      </DetailPane>
    </div>
  );
}
