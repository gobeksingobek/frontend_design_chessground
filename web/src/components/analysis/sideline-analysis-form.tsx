"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

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
  return input
    .split(/[\s,]+/)
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

function parseMovePly(input: string): number | null {
  if (!input.trim()) return null;
  const parsed = Number(input);
  if (!Number.isFinite(parsed) || parsed < 1) return null;
  return Math.floor(parsed);
}

function evalSummary(metadata: SidelineEvalMetadata | null): string | null {
  if (!metadata) return null;
  if (metadata.confidence_tag === "unavailable") {
    return "Quick eval unavailable. Queue submission is still allowed.";
  }
  if (metadata.cpl_estimate === null) {
    return "Quick eval incomplete. Queue submission is still allowed.";
  }
  if (metadata.cpl_estimate <= 30) {
    return `Good candidate (estimated CPL ${Math.round(metadata.cpl_estimate)}).`;
  }
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
      if (!baseFieldsValid || movePly === null) {
        throw new Error("Enter game id, move ply, FEN, and at least one UCI move");
      }

      const idempotencyKey = `game-${gameId}-ply-${movePly}-${Date.now()}`;
      const metadata =
        quickEval && quickEval.candidate_move_uci === candidateMove
          ? quickEval
          : buildUnavailableMetadata(candidateMove ?? null);

      return createSideline(
        {
          game_id: gameId.trim(),
          move_ply: movePly,
          fen: fen.trim(),
          branch_moves: branchMoves,
          eval_metadata: metadata,
        },
        idempotencyKey,
      );
    },
    onSuccess: (result) => {
      setCreatedSideline(result.id);
      queryClient.invalidateQueries({ queryKey: ["sidelines", 20] });
    },
  });

  return (
    <div className="stack">
      <h4>{title}</h4>

      <label>
        Game id
        <input
          value={gameId}
          onChange={(event) => setGameId(event.target.value)}
          disabled={Boolean(lockedFields.gameId)}
          placeholder="game-12345"
        />
      </label>

      <label>
        Move ply
        <input
          value={movePlyInput}
          onChange={(event) => setMovePlyInput(event.target.value)}
          disabled={Boolean(lockedFields.movePly)}
          inputMode="numeric"
          placeholder="12"
        />
      </label>

      <label>
        Starting FEN
        <input
          value={fen}
          onChange={(event) => setFen(event.target.value)}
          disabled={Boolean(lockedFields.fen)}
          placeholder="rnbqkbnr/pppppppp/8/8/..."
        />
      </label>

      <label>
        Branch moves (UCI, comma or whitespace separated)
        <input
          value={branchMovesInput}
          onChange={(event) => setBranchMovesInput(event.target.value)}
          placeholder="e2e4 e7e5 g1f3"
        />
      </label>

      {quickEvalLoading ? <small>Running quick Stockfish eval...</small> : null}
      {!quickEvalLoading && quickEval ? <p className={isGoodCandidate(quickEval) ? "ok" : "warn"}>{evalSummary(quickEval)}</p> : null}
      {!quickEvalLoading && quickEval ? (
        <small>
          Candidate: {quickEval.candidate_move_uci ?? "-"} | Depth used: {quickEval.eval_depth ?? "-"} | Time used:{" "}
          {quickEval.eval_time_ms ?? "-"} ms | Confidence: {quickEval.confidence_tag}
        </small>
      ) : null}

      <button type="button" onClick={() => createSidelineMutation.mutate()} disabled={createSidelineMutation.isPending || !baseFieldsValid}>
        {createSidelineMutation.isPending ? "Queueing..." : "Queue sideline"}
      </button>

      {createSidelineMutation.isError ? <p>Failed: {(createSidelineMutation.error as Error).message}</p> : null}
      {createdSideline ? <p>Queued sideline request: {createdSideline}</p> : null}
    </div>
  );
}
