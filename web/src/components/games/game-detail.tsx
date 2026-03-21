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
import { cn } from "@/lib/cn";
import { getGame } from "@/lib/api-client";

export function applyCursorKey(key: string, current: number, max: number): number { if (key === "ArrowRight") return Math.min(max, current + 1); if (key === "ArrowLeft") return Math.max(0, current - 1); if (key === "ArrowUp" || key === "End") return max; if (key === "ArrowDown" || key === "Home") return 0; return current; }
function shouldIgnoreKeyboardEvent(event: KeyboardEvent | ReactKeyboardEvent): boolean { const target = event.target; if (!(target instanceof HTMLElement)) return false; const tagName = target.tagName; if (tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT") return true; return target.isContentEditable; }

export function GameDetail({ gameId, initialPly }: { gameId: number; initialPly: number | null }) {
  const [cursorIndex, setCursorIndex] = useState(0);
  const { data, isLoading, error } = useQuery({ queryKey: ["game", gameId], queryFn: () => getGame(gameId) });
  const moves = useMemo(() => data?.moves ?? [], [data]);
  useEffect(() => { if (!moves.length) { setCursorIndex(0); return; } if (initialPly !== null) { const moveIndex = moves.findIndex((move) => move.ply === initialPly); if (moveIndex >= 0) { setCursorIndex(moveIndex + 1); return; } } setCursorIndex(0); }, [gameId, initialPly, moves]);
  const selectedMove = useMemo(() => (cursorIndex === 0 ? null : moves[cursorIndex - 1] ?? null), [moves, cursorIndex]);
  const selectedPly = selectedMove?.ply ?? null;
  const boardFen = useMemo(() => (!moves.length || cursorIndex === 0 ? undefined : selectedMove?.fen ?? undefined), [moves.length, cursorIndex, selectedMove]);
  const hasEvalData = selectedMove?.pre_eval_cp !== null || selectedMove?.post_eval_cp !== null;
  const navigateNext = useCallback(() => { setCursorIndex((current) => Math.min(moves.length, current + 1)); }, [moves.length]);
  const navigatePrev = useCallback(() => { setCursorIndex((current) => Math.max(0, current - 1)); }, []);
  const navigateStart = useCallback(() => { setCursorIndex(0); }, []);
  const navigateEnd = useCallback(() => { setCursorIndex(moves.length); }, [moves.length]);
  const onKeyNavigate = useCallback((event: KeyboardEvent | ReactKeyboardEvent) => { if (shouldIgnoreKeyboardEvent(event)) return; const nextCursor = applyCursorKey(event.key, cursorIndex, moves.length); if (nextCursor !== cursorIndex) { event.preventDefault(); setCursorIndex(nextCursor); } }, [cursorIndex, moves.length]);
  if (isLoading) return <p className="text-sm text-muted-foreground">Loading game detail...</p>;
  if (error) return <p className="text-sm text-danger">Failed to load game detail: {(error as Error).message}</p>;

  return (
    <div className="grid gap-section-gap" onKeyDown={onKeyNavigate} tabIndex={0}>
      <DetailPane title="Game header" description="Navigate between adjacent games or inspect the raw PGN header payload.">
        <div className="flex flex-wrap items-center justify-between gap-control-gap">
          <div className="grid gap-xs">
            <p className="text-sm font-medium text-foreground">Game #{gameId}</p>
            <p className="text-sm text-muted-foreground">Use the move table or keyboard shortcuts to step through the position history.</p>
          </div>
          <DenseControlRow>
            {data?.prev_game_id ? <Link className="text-sm text-primary hover:text-secondary" href={{ pathname: `/games/${data.prev_game_id}`, query: selectedPly ? { ply: String(selectedPly) } : {} }}>← Previous game</Link> : <span className="text-sm text-muted-foreground/70">← Previous game</span>}
            {data?.next_game_id ? <Link className="text-sm text-primary hover:text-secondary" href={{ pathname: `/games/${data.next_game_id}`, query: selectedPly ? { ply: String(selectedPly) } : {} }}>Next game →</Link> : <span className="text-sm text-muted-foreground/70">Next game →</span>}
          </DenseControlRow>
        </div>
        <pre className="overflow-x-auto rounded-lg border border-border bg-muted p-4 font-mono text-xs text-muted-foreground">{JSON.stringify(data?.header, null, 2)}</pre>
      </DetailPane>

      <div className="grid gap-grid-gap xl:grid-cols-board">
        <DetailPane title="Selected position" description="Review the board state and queue sideline analysis from any move with a FEN.">
          <ChessBoard fen={boardFen} title="Selected game position" currentPlyIndex={cursorIndex} onNavigateNext={navigateNext} onNavigatePrev={navigatePrev} onNavigateStart={navigateStart} onNavigateEnd={navigateEnd} onMoveAttempt={({ uci }) => { const nextMove = moves[cursorIndex]; if (nextMove?.uci_move === uci) navigateNext(); }} />
          <FilterPanel title="Move selector" description="Keep dense controls compact while the board and detail regions stay spacious.">
            <label className="grid max-w-md gap-xs text-sm text-muted-foreground">Move ply<Select value={selectedPly ?? ""} onChange={(event) => { const ply = event.target.value ? Number(event.target.value) : null; if (ply === null) { setCursorIndex(0); return; } const moveIndex = moves.findIndex((move) => move.ply === ply); setCursorIndex(moveIndex >= 0 ? moveIndex + 1 : 0); }}><option value="">Initial position</option>{moves.map((move) => <option key={move.ply} value={move.ply}>Ply {move.ply} - {move.san_move ?? move.uci_move ?? "-"}</option>)}</Select></label>
          </FilterPanel>
          {selectedMove?.fen ? <p className="text-sm"><Link className="text-primary hover:text-secondary" href={{ pathname: "/analysis", query: { game_id: String(gameId), move_ply: String(selectedMove.ply), fen: selectedMove.fen } }}>Open in /analysis with this position</Link></p> : null}
          {selectedMove?.fen ? <SidelineAnalysisForm key={`${selectedMove.ply}-${selectedMove.fen}`} title="Queue sideline from this game move" initialGameId={String(gameId)} initialMovePly={selectedMove.ply} initialFen={selectedMove.fen} lockedFields={{ gameId: true, movePly: true, fen: true }} /> : <EmptyState title="Select a move to analyze" description="Choose a move with an available FEN to queue a quick sideline evaluation from this game." />}
        </DetailPane>

        <div className="grid gap-grid-gap">
          {selectedMove ? <div className="grid gap-grid-gap xl:grid-cols-3"><DetailPane title="Selected ply details"><div className="grid gap-sm text-sm text-foreground"><p>Ply {selectedMove.ply}: {selectedMove.san_move ?? selectedMove.uci_move ?? "-"}</p><p>Quality: <MoveQualityBadge label={selectedMove.quality_label} /></p><p className={cn("text-sm font-medium", selectedMove.your_cpl !== null && selectedMove.your_cpl > 120 ? "text-danger" : "text-success")}>Your CPL: {selectedMove.your_cpl ?? "-"}</p></div></DetailPane>{hasEvalData ? <><EvalBar evalCp={selectedMove.pre_eval_cp} title="Before move" /><EvalBar evalCp={selectedMove.post_eval_cp} title="After move" /></> : <DetailPane title="Eval panel" description="No pre/post eval values are available for the selected move."><p className="text-sm text-muted-foreground">Evaluation data will appear here when pre/post engine scores are available.</p></DetailPane>}</div> : <EmptyState title="No move selected" description="Select a move from the table to populate the detail pane and evaluation cards." />}
        </div>
      </div>

      <DetailPane title="Moves" description="Click a row or use arrow keys while focused to step through the game.">
        {moves.length === 0 ? <EmptyState title="No moves recorded" description="This game does not have move data available yet." /> : <Table>
          <TableHead><tr><Th>Ply</Th><Th>SAN</Th><Th>UCI</Th><Th>Class</Th><Th>Quality</Th><Th>Your CPL</Th></tr></TableHead>
          <TableBody>{moves.map((move) => <tr key={move.ply} className={cn("cursor-pointer transition hover:bg-hover", move.ply === selectedPly && "bg-selection")} onClick={() => { const moveIndex = moves.findIndex((candidate) => candidate.ply === move.ply); setCursorIndex(moveIndex + 1); }}><Td className={move.ply === selectedPly ? "text-selection-foreground" : undefined}>{move.ply}</Td><Td className={move.ply === selectedPly ? "text-selection-foreground" : undefined}>{move.san_move ?? "-"}</Td><Td className={move.ply === selectedPly ? "text-selection-foreground" : undefined}>{move.uci_move ?? "-"}</Td><Td className={move.ply === selectedPly ? "text-selection-foreground" : undefined}>{move.repertoire_class ?? "-"}</Td><Td><MoveQualityBadge label={move.quality_label} /></Td><Td className={cn(move.ply === selectedPly && "text-selection-foreground", move.your_cpl !== null && move.your_cpl > 120 ? "text-danger" : "text-success")}>{move.your_cpl ?? "-"}</Td></tr>)}</TableBody>
        </Table>}
      </DetailPane>
    </div>
  );
}
