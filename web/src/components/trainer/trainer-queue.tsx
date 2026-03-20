"use client";

import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { TrainerSessionAnswerResponse, TrainerSessionItem } from "@/lib/types";

export type TrainerPhase = "prompt" | "attempt" | "reveal" | "grade" | "next";
export function shouldShowRemediation(result: TrainerSessionAnswerResponse | null): boolean { return result?.outcome === "incorrect" && Boolean(result.remediation); }
export function shouldShowRetryRequired(result: TrainerSessionAnswerResponse | null): boolean { return shouldShowRemediation(result) && Boolean(result?.remediation?.retry_required); }
export function resolveNextPhase(current: TrainerPhase, outcome: "correct" | "incorrect"): TrainerPhase { if (current === "prompt") return "attempt"; if (current === "attempt") return outcome === "incorrect" ? "reveal" : "grade"; if (current === "reveal") return "grade"; if (current === "grade") return "next"; return "prompt"; }

interface TrainerQueueProps { mode: "learn" | "review"; sessionId: string | null; item: TrainerSessionItem | null; onStart: () => void; onAnswer: (moveUci: string, elapsedMs: number) => Promise<TrainerSessionAnswerResponse>; onNext: () => void; statusText?: string | null; }

export function TrainerQueue({ mode, sessionId, item, onStart, onAnswer, onNext, statusText }: TrainerQueueProps) {
  const [phase, setPhase] = useState<TrainerPhase>("prompt");
  const [attemptUci, setAttemptUci] = useState("");
  const [phaseStartedAt, setPhaseStartedAt] = useState<number>(Date.now());
  const [result, setResult] = useState<TrainerSessionAnswerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canAnswer = Boolean(sessionId && item && phase === "attempt" && attemptUci.trim());
  const phaseHelp = useMemo(() => ({ prompt: "Review prompt and continue to attempt.", attempt: "Submit your move attempt in UCI format.", reveal: "Review remediation details before grading.", grade: "Answer has been graded.", next: "Continue to the next training item." }[phase]), [phase]);
  const remediation = result?.remediation ?? null;

  return (
    <Card>
      <h3 className="text-base font-semibold">Trainer queue flow</h3>
      <div className="flex flex-wrap gap-2"><Badge tone="accent">Mode: {mode}</Badge><Badge>Stage: {phase}</Badge></div>
      <small className="text-text-muted">{phaseHelp}</small>

      {!sessionId ? <div className="pt-2"><Button type="button" variant="primary" onClick={() => { setPhase("prompt"); setResult(null); setError(null); onStart(); }}>Create session</Button></div> : null}

      {sessionId && item ? (
        <Card className="gap-3 border-border/80 bg-panel-muted">
          <small className="text-text-muted">Session: {sessionId}</small>
          <p className="text-sm text-text">{item.prompt}</p>
          <p className="text-sm text-text-subtle"><strong>Branch:</strong> {item.branch_id} · <strong>Difficulty:</strong> {item.difficulty}</p>
          <label className="grid gap-2 text-sm text-text-subtle">Attempt UCI<Input value={attemptUci} onChange={(event) => setAttemptUci(event.target.value)} placeholder="e2e4" /></label>
          <div className="flex flex-wrap gap-2 pt-1">
            <Button type="button" onClick={() => { setPhase("attempt"); setPhaseStartedAt(Date.now()); }}>Begin attempt</Button>
            <Button type="button" variant="primary" disabled={!canAnswer} onClick={async () => { if (!attemptUci.trim()) return; try { const response = await onAnswer(attemptUci.trim(), Date.now() - phaseStartedAt); setResult(response); setAttemptUci(""); setError(null); setPhase(resolveNextPhase("attempt", response.outcome)); } catch (submitError) { setError((submitError as Error).message); } }}>Submit attempt</Button>
            {phase === "reveal" ? <Button type="button" onClick={() => setPhase("grade")}>Continue to grade</Button> : null}
            {phase === "grade" ? <Button type="button" onClick={() => setPhase("next")}>Show next action</Button> : null}
            {phase === "next" ? <Button type="button" onClick={() => { setPhase("prompt"); setResult(null); onNext(); }}>Next item</Button> : null}
          </div>
        </Card>
      ) : null}

      {shouldShowRemediation(result) && remediation ? (
        <Card className="gap-2 border-warning/30 bg-warning/10">
          <p><strong>Best move:</strong> {remediation.best_move_uci}</p>
          <p><strong>Principal variation:</strong> {remediation.principal_variation.join(" ")}</p>
          <p className="text-sm text-text-subtle">{remediation.explanation_markdown}</p>
          {shouldShowRetryRequired(result) ? <Button type="button" onClick={() => { setPhase("attempt"); setPhaseStartedAt(Date.now()); }}>Retry required</Button> : null}
        </Card>
      ) : null}

      {result ? <p className="text-sm text-text-subtle">Outcome: {result.outcome} · Grade: {result.grade} · State: {result.item_state}</p> : null}
      {statusText ? <p className="text-sm text-text-muted">{statusText}</p> : null}
      {error ? <p className="text-sm text-danger">{error}</p> : null}
    </Card>
  );
}
