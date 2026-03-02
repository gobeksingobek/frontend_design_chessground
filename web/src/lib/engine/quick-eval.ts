import type { EvalConfidenceTag, SidelineEvalMetadata } from "@/lib/types";

import { stockfishClient } from "@/lib/engine/stockfish-client";

export const QUICK_EVAL_DEPTH = 14;
export const QUICK_EVAL_MOVETIME_MS = 500;
const GOOD_CANDIDATE_CPL = 30;

interface QuickEvalArgs {
  fen: string;
  candidateMoveUci: string;
}

function classifyConfidence(depth: number | null): EvalConfidenceTag {
  if (depth === null) return "unavailable";
  if (depth >= QUICK_EVAL_DEPTH) return "high";
  if (depth >= 10) return "medium";
  return "low";
}

function toRoundedMs(value: number): number {
  return Math.max(0, Math.round(value));
}

export function buildUnavailableMetadata(candidateMoveUci: string | null): SidelineEvalMetadata {
  return {
    cpl_estimate: null,
    eval_depth: null,
    eval_time_ms: null,
    confidence_tag: "unavailable",
    candidate_move_uci: candidateMoveUci,
    budget_depth: QUICK_EVAL_DEPTH,
    budget_time_ms: QUICK_EVAL_MOVETIME_MS,
    engine: "stockfish_wasm",
  };
}

export function isGoodCandidate(metadata: SidelineEvalMetadata | null): boolean {
  if (metadata?.cpl_estimate == null) {
    return false;
  }
  return metadata.cpl_estimate <= GOOD_CANDIDATE_CPL;
}

export async function estimateQuickEvalMetadata({
  fen,
  candidateMoveUci,
}: QuickEvalArgs): Promise<SidelineEvalMetadata> {
  const candidate = candidateMoveUci.trim().toLowerCase();
  if (!fen.trim() || !candidate) {
    return buildUnavailableMetadata(candidate || null);
  }

  try {
    const result = await stockfishClient.analyzeMoveDelta(fen, candidate, QUICK_EVAL_DEPTH, QUICK_EVAL_MOVETIME_MS);
    const bestCp = result.best.score_cp;
    const candidateCp = result.candidate.score_cp;

    if (bestCp === null || candidateCp === null) {
      return buildUnavailableMetadata(candidate);
    }

    const cplEstimate = Math.max(0, bestCp - candidateCp);
    const evalDepth = Math.min(result.best.depth ?? QUICK_EVAL_DEPTH, result.candidate.depth ?? QUICK_EVAL_DEPTH);

    return {
      cpl_estimate: cplEstimate,
      eval_depth: evalDepth,
      eval_time_ms: toRoundedMs(result.total_elapsed_ms),
      confidence_tag: classifyConfidence(evalDepth),
      candidate_move_uci: candidate,
      budget_depth: QUICK_EVAL_DEPTH,
      budget_time_ms: QUICK_EVAL_MOVETIME_MS,
      engine: "stockfish_wasm",
    };
  } catch {
    return buildUnavailableMetadata(candidate);
  }
}
