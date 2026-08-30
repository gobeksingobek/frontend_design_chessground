"use client";

import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DenseControlRow, DetailPane, EmptyState, FilterPanel } from "@/components/ui/page-patterns";
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
  const [phaseStartedAt, setPhaseStartedAt] = useState<number>(() => Date.now());
  const [result, setResult] = useState<TrainerSessionAnswerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canAnswer = Boolean(sessionId && item && phase === "attempt" && attemptUci.trim());
  const phaseHelp = useMemo(() => ({ prompt: "Review prompt and continue to attempt.", attempt: "Submit your move attempt in UCI format.", reveal: "Review remediation details before grading.", grade: "Answer has been graded.", next: "Continue to the next training item." }[phase]), [phase]);
  const remediation = result?.remediation ?? null;

  return (
    <DetailPane title="Trainer queue flow" description="Keep the page rhythm spacious while the answer controls remain compact and task-focused.">
      <DenseControlRow><Badge tone="accent">Mode: {mode}</Badge><Badge>Stage: {phase}</Badge></DenseControlRow>
      <small className="text-muted-foreground">{phaseHelp}</small>

      {!sessionId ? <EmptyState title="No active training session" description="Create a session to start stepping through the queue." action={<Button type="button" variant="primary" onClick={() => { setPhase("prompt"); setResult(null); setError(null); onStart(); }}>Create session</Button>} /> : null}

      {sessionId && item ? (
        <DetailPane title="Current prompt" description="Work through the prompt, submit an answer, and move to the next training item.">
          <div className="grid gap-control-gap text-sm">
            <small className="text-muted-foreground">Session: {sessionId}</small>
            <p className="text-foreground">{item.prompt}</p>
            <p className="text-muted-foreground"><strong>Branch:</strong> {item.branch_id} · <strong>Difficulty:</strong> {item.difficulty}</p>
          </div>
          <FilterPanel title="Answer controls" description="Dense inputs are tightened here without compressing the surrounding page sections.">
            <div className="grid gap-control-gap">
              <label className="grid gap-xs text-sm text-muted-foreground">Attempt UCI<Input value={attemptUci} onChange={(event) => setAttemptUci(event.target.value)} placeholder="e2e4" /></label>
              <DenseControlRow>
                <Button type="button" onClick={() => { setPhase("attempt"); setPhaseStartedAt(Date.now()); }}>Begin attempt</Button>
                <Button type="button" variant="primary" disabled={!canAnswer} onClick={async () => { if (!attemptUci.trim()) return; try { const response = await onAnswer(attemptUci.trim(), Date.now() - phaseStartedAt); setResult(response); setAttemptUci(""); setError(null); setPhase(resolveNextPhase("attempt", response.outcome)); } catch (submitError) { setError((submitError as Error).message); } }}>Submit attempt</Button>
                {phase === "reveal" ? <Button type="button" onClick={() => setPhase("grade")}>Continue to grade</Button> : null}
                {phase === "grade" ? <Button type="button" onClick={() => setPhase("next")}>Show next action</Button> : null}
                {phase === "next" ? <Button type="button" onClick={() => { setPhase("prompt"); setResult(null); onNext(); }}>Next item</Button> : null}
              </DenseControlRow>
            </div>
          </FilterPanel>
        </DetailPane>
      ) : null}

      {shouldShowRemediation(result) && remediation ? (
        <DetailPane title="Remediation" description="Review the best move and principal variation before trying again or continuing.">
          <div className="grid gap-control-gap text-sm">
            <p><strong>Best move:</strong> {remediation.best_move_uci}</p>
            <p><strong>Principal variation:</strong> {remediation.principal_variation.join(" ")}</p>
            <p className="text-muted-foreground">{remediation.explanation_markdown}</p>
          </div>
          {shouldShowRetryRequired(result) ? <Button type="button" onClick={() => { setPhase("attempt"); setPhaseStartedAt(Date.now()); }}>Retry required</Button> : null}
        </DetailPane>
      ) : null}

      {result ? <p className="text-sm text-muted-foreground">Outcome: {result.outcome} · Grade: {result.grade} · State: {result.item_state}</p> : null}
      {statusText ? <p className="text-sm text-muted-foreground">{statusText}</p> : null}
      {error ? <p className="text-sm text-danger">{error}</p> : null}
    </DetailPane>
  );
}
