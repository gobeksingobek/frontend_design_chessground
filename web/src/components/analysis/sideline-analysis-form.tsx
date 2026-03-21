"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { createSideline } from "@/lib/api-client";
import { buildUnavailableMetadata, estimateQuickEvalMetadata, isGoodCandidate } from "@/lib/engine/quick-eval";
import type { SidelineEvalMetadata } from "@/lib/types";

interface LockedFields {
  gameId?: boolean;
  movePly?: boolean;
  fen?: boolean;
}

interface SidelineAnalysisFormProps {
  title?: string;
  initialGameId?: string;
  initialMovePly?: number | null;
  initialFen?: string;
  initialBranchMoves?: string;
  lockedFields?: LockedFields;
}

function parseBranchMoves(input: string): string[] {
  return input.split(/[\s,]+/).map((item) => item.trim().toLowerCase()).filter(Boolean);
}

function parseMovePly(input: string): number | null {
  if (!input.trim()) return null;
  const parsed = Number(input);
  if (!Number.isFinite(parsed) || parsed < 1) return null;
  return Math.floor(parsed);
}

function evalSummary(metadata: SidelineEvalMetadata | null): string | null {
  if (!metadata) return null;
  if (metadata.confidence_tag === "unavailable") return "Quick eval unavailable. Queue submission is still allowed.";
  if (metadata.cpl_estimate === null) return "Quick eval incomplete. Queue submission is still allowed.";
  if (metadata.cpl_estimate <= 30) return `Good candidate (estimated CPL ${Math.round(metadata.cpl_estimate)}).`;
  return `Warning: estimated CPL ${Math.round(metadata.cpl_estimate)} (>30). You can still queue this move.`;
}

export function SidelineAnalysisForm({
  title = "Queue sideline analysis",
  initialGameId = "",
  initialMovePly = null,
  initialFen = "",
  initialBranchMoves = "",
  lockedFields = {},
}: SidelineAnalysisFormProps) {
  const queryClient = useQueryClient();
  const [gameId, setGameId] = useState(initialGameId);
  const [movePlyInput, setMovePlyInput] = useState(initialMovePly ? String(initialMovePly) : "");
  const [fen, setFen] = useState(initialFen);
  const [branchMovesInput, setBranchMovesInput] = useState(initialBranchMoves);
  const [createdSideline, setCreatedSideline] = useState<string | null>(null);
  const [quickEval, setQuickEval] = useState<SidelineEvalMetadata | null>(null);
  const [quickEvalLoading, setQuickEvalLoading] = useState(false);

  useEffect(() => {
    if (!lockedFields.gameId) return;
    setGameId(initialGameId);
  }, [initialGameId, lockedFields.gameId]);
  useEffect(() => {
    if (!lockedFields.movePly) return;
    setMovePlyInput(initialMovePly ? String(initialMovePly) : "");
  }, [initialMovePly, lockedFields.movePly]);
  useEffect(() => {
    if (!lockedFields.fen) return;
    setFen(initialFen);
  }, [initialFen, lockedFields.fen]);

  const branchMoves = useMemo(() => parseBranchMoves(branchMovesInput), [branchMovesInput]);
  const candidateMove = branchMoves[0] ?? null;
  const movePly = parseMovePly(movePlyInput);
  const baseFieldsValid = Boolean(gameId.trim() && fen.trim() && movePly !== null && branchMoves.length > 0);
  const movePlyError = movePlyInput && movePly === null ? "Move ply must be a positive whole number." : null;
  const branchMovesError = branchMovesInput.trim() && branchMoves.length === 0 ? "Enter at least one valid UCI move." : null;

  useEffect(() => {
    let cancelled = false;
    if (!fen.trim() || !candidateMove) {
      setQuickEval(null);
      setQuickEvalLoading(false);
      return;
    }
    setQuickEvalLoading(true);
    const timer = window.setTimeout(async () => {
      const metadata = await estimateQuickEvalMetadata({ fen, candidateMoveUci: candidateMove });
      if (cancelled) return;
      setQuickEval(metadata);
      setQuickEvalLoading(false);
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [fen, candidateMove]);

  const createSidelineMutation = useMutation({
    mutationFn: async () => {
      if (!baseFieldsValid || movePly === null) throw new Error("Enter game id, move ply, FEN, and at least one UCI move");
      const idempotencyKey = `game-${gameId}-ply-${movePly}-${Date.now()}`;
      const metadata = quickEval && quickEval.candidate_move_uci === candidateMove ? quickEval : buildUnavailableMetadata(candidateMove ?? null);
      return createSideline({ game_id: gameId.trim(), move_ply: movePly, fen: fen.trim(), branch_moves: branchMoves, eval_metadata: metadata }, idempotencyKey);
    },
    onSuccess: (result) => {
      setCreatedSideline(result.id);
      queryClient.invalidateQueries({ queryKey: ["sidelines", 20] });
    },
  });

  return (
    <div className="grid gap-4">
      <h4 className="text-base font-semibold text-text">{title}</h4>
      <FormField label="Game id" helpText="Use the source game identifier to link this sideline back to the original record."><Input value={gameId} onChange={(event) => setGameId(event.target.value)} disabled={Boolean(lockedFields.gameId)} placeholder="game-12345" aria-invalid={!gameId.trim() && createSidelineMutation.isError} /></FormField>
      <FormField label="Move ply" helpText="This must be the ply number of the source position." error={movePlyError}><Input value={movePlyInput} onChange={(event) => setMovePlyInput(event.target.value)} disabled={Boolean(lockedFields.movePly)} inputMode="numeric" placeholder="12" aria-invalid={Boolean(movePlyError)} /></FormField>
      <FormField label="Starting FEN" helpText="Paste the exact board state that should seed the variation search."><Input value={fen} onChange={(event) => setFen(event.target.value)} disabled={Boolean(lockedFields.fen)} placeholder="rnbqkbnr/pppppppp/8/8/..." aria-invalid={!fen.trim() && createSidelineMutation.isError} /></FormField>
      <FormField label="Branch moves" helpText="Enter candidate UCI moves separated by commas or spaces. The first move is used for quick evaluation." error={branchMovesError}><Input value={branchMovesInput} onChange={(event) => setBranchMovesInput(event.target.value)} placeholder="e2e4 e7e5 g1f3" aria-invalid={Boolean(branchMovesError)} /></FormField>
      {quickEvalLoading ? <small className="text-text-muted">Running quick Stockfish eval...</small> : null}
      {!quickEvalLoading && quickEval ? <Badge tone={isGoodCandidate(quickEval) ? "success" : "warning"}>{evalSummary(quickEval)}</Badge> : null}
      {!quickEvalLoading && quickEval ? <small className="text-text-muted">Candidate: {quickEval.candidate_move_uci ?? "-"} · Depth used: {quickEval.eval_depth ?? "-"} · Time used: {quickEval.eval_time_ms ?? "-"} ms · Confidence: {quickEval.confidence_tag}</small> : null}
      <div className="flex flex-wrap gap-2"><Button type="button" size="lg" variant="primary" onClick={() => createSidelineMutation.mutate()} disabled={createSidelineMutation.isPending || !baseFieldsValid}>{createSidelineMutation.isPending ? "Queueing..." : "Queue sideline"}</Button><Button type="button" variant="ghost" onClick={() => { setBranchMovesInput(initialBranchMoves); setCreatedSideline(null); }}>Reset moves</Button></div>
      {createSidelineMutation.isError ? <p className="text-sm text-danger">Failed: {(createSidelineMutation.error as Error).message}</p> : null}
      {createdSideline ? <p className="text-sm text-success">Queued sideline request: {createdSideline}</p> : null}
    </div>
  );
}
