"use client";

import { useMemo, useState } from "react";

import type { TrainerSessionAnswerResponse, TrainerSessionItem } from "@/lib/types";

export type TrainerPhase = "prompt" | "attempt" | "reveal" | "grade" | "next";

export function resolveNextPhase(current: TrainerPhase, outcome: "correct" | "incorrect"): TrainerPhase {
  if (current === "prompt") return "attempt";
  if (current === "attempt") return outcome === "incorrect" ? "reveal" : "grade";
  if (current === "reveal") return "grade";
  if (current === "grade") return "next";
  return "prompt";
}

interface TrainerQueueProps {
  mode: "learn" | "review";
  sessionId: string | null;
  item: TrainerSessionItem | null;
  onStart: () => void;
  onAnswer: (moveUci: string, elapsedMs: number) => Promise<TrainerSessionAnswerResponse>;
  onNext: () => void;
  statusText?: string | null;
}

export function TrainerQueue({ mode, sessionId, item, onStart, onAnswer, onNext, statusText }: TrainerQueueProps) {
  const [phase, setPhase] = useState<TrainerPhase>("prompt");
  const [attemptUci, setAttemptUci] = useState("");
  const [phaseStartedAt, setPhaseStartedAt] = useState<number>(Date.now());
  const [result, setResult] = useState<TrainerSessionAnswerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canAnswer = Boolean(sessionId && item && phase === "attempt" && attemptUci.trim());

  const phaseHelp = useMemo(() => {
    switch (phase) {
      case "prompt":
        return "Review prompt and continue to attempt.";
      case "attempt":
        return "Submit your move attempt in UCI format.";
      case "reveal":
        return "Review remediation details before grading.";
      case "grade":
        return "Answer has been graded.";
      case "next":
        return "Continue to the next training item.";
    }
  }, [phase]);

  return (
    <div className="card">
      <h3>Trainer queue flow</h3>
      <p>
        <strong>Mode:</strong> {mode}
      </p>
      <p>
        <strong>Stage:</strong> {phase}
      </p>
      <small>{phaseHelp}</small>

      {!sessionId ? (
        <div style={{ marginTop: 10 }}>
          <button type="button" onClick={() => { setPhase("prompt"); setResult(null); setError(null); onStart(); }}>
            Create session
          </button>
        </div>
      ) : null}

      {sessionId && item ? (
        <div className="card" style={{ marginTop: 10 }}>
          <small>Session: {sessionId}</small>
          <p>{item.prompt}</p>
          <p>
            <strong>Branch:</strong> {item.branch_id} · <strong>Difficulty:</strong> {item.difficulty}
          </p>
          <label>
            Attempt UCI
            <input value={attemptUci} onChange={(event) => setAttemptUci(event.target.value)} placeholder="e2e4" />
          </label>
          <div className="stack" style={{ marginTop: 8 }}>
            <button
              type="button"
              onClick={() => {
                setPhase("attempt");
                setPhaseStartedAt(Date.now());
              }}
            >
              Begin attempt
            </button>
            <button
              type="button"
              disabled={!canAnswer}
              onClick={async () => {
                if (!attemptUci.trim()) return;
                try {
                  const response = await onAnswer(attemptUci.trim(), Date.now() - phaseStartedAt);
                  setResult(response);
                  setAttemptUci("");
                  setError(null);
                  setPhase(resolveNextPhase("attempt", response.outcome));
                } catch (submitError) {
                  setError((submitError as Error).message);
                }
              }}
            >
              Submit attempt
            </button>
            {phase === "reveal" ? <button type="button" onClick={() => setPhase("grade")}>Continue to grade</button> : null}
            {phase === "grade" ? <button type="button" onClick={() => setPhase("next")}>Show next action</button> : null}
            {phase === "next" ? <button type="button" onClick={() => { setPhase("prompt"); setResult(null); onNext(); }}>Next item</button> : null}
          </div>
        </div>
      ) : null}

      {result?.remediation ? (
        <div className="card" style={{ marginTop: 10 }}>
          <p>
            <strong>Best move:</strong> {result.remediation.best_move_uci}
          </p>
          <p>{result.remediation.explanation_markdown}</p>
        </div>
      ) : null}

      {result ? <p>Outcome: {result.outcome} · Grade: {result.grade} · State: {result.item_state}</p> : null}
      {statusText ? <p>{statusText}</p> : null}
      {error ? <p className="warn">{error}</p> : null}
    </div>
  );
}
