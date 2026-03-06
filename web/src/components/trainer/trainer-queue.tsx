"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createTrainerSession, getTrainerQueueV2, submitTrainerSessionAnswer } from "@/lib/api-client";

export type TrainerPhase = "prompt" | "user_attempt" | "reveal_explanation" | "grading" | "next_item_transition";

export function resolveNextPhase(current: TrainerPhase, isCorrect: boolean, completed: boolean): TrainerPhase {
  if (completed) return "next_item_transition";
  if (!isCorrect) return "reveal_explanation";
  if (current === "prompt") return "user_attempt";
  return "grading";
}

export function TrainerQueue() {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"learn" | "review">("review");
  const [phase, setPhase] = useState<TrainerPhase>("prompt");
  const [attemptUci, setAttemptUci] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [selectedLineId, setSelectedLineId] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  const queue = useQuery({
    queryKey: ["trainer", "queue-list", mode],
    queryFn: () => getTrainerQueueV2(mode),
  });

  const items = queue.data?.items ?? [];
  const activeLineId = selectedLineId ?? items[0]?.line_id ?? null;

  const sessionStart = useMutation({
    mutationFn: createTrainerSession,
    onSuccess: (session) => {
      setActiveSessionId(session.session_id);
      setFeedback(session.next_step.explanation ?? null);
      setPhase("prompt");
      setAttemptUci("");
      queryClient.invalidateQueries({ queryKey: ["trainer", "queue-list"] });
    },
  });

  const answer = useMutation({
    mutationFn: ({ sessionId, answerUci }: { sessionId: string; answerUci: string }) =>
      submitTrainerSessionAnswer(sessionId, { answer_uci: answerUci }),
    onSuccess: (result) => {
      setFeedback(result.feedback);
      setPhase(resolveNextPhase(phase, result.is_correct, result.completed));
      if (result.completed) {
        setActiveSessionId(null);
        queryClient.invalidateQueries({ queryKey: ["trainer", "queue-list"] });
      }
      if (!result.is_correct) {
        setFeedback(`${result.feedback} Expected: ${result.expected_move_uci ?? "unknown"}. ${result.next_step.explanation ?? ""}`);
      }
      setAttemptUci("");
    },
  });

  const canStart = Boolean(activeLineId) && !activeSessionId;
  const activeExpected = answer.data?.next_step.expected_move_uci;

  const phaseHelp = useMemo(() => {
    switch (phase) {
      case "prompt":
        return "Prompt: prepare for the repertoire move.";
      case "user_attempt":
        return "User attempt: submit a UCI move.";
      case "reveal_explanation":
        return "Reveal/explanation: remediation after an incorrect answer.";
      case "grading":
        return "Grading: answer accepted, state updated.";
      case "next_item_transition":
        return "Next item transition: start the next queue item.";
    }
  }, [phase]);

  if (queue.isLoading) return <p>Loading trainer queue...</p>;
  if (queue.error) return <p className="warn">Failed to load trainer queue: {(queue.error as Error).message}</p>;

  return (
    <div className="card">
      <h3>Trainer queue flow</h3>
      <label>
        Mode
        <select value={mode} onChange={(event) => { setMode(event.target.value as "learn" | "review"); setActiveSessionId(null); setPhase("prompt"); }}>
          <option value="learn">Learn</option>
          <option value="review">Review</option>
        </select>
      </label>
      <p><strong>Phase:</strong> {phase}</p>
      <small>{phaseHelp}</small>

      <div className="stack" style={{ marginTop: 8 }}>
        {items.slice(0, 8).map((item) => (
          <button key={item.line_id} type="button" onClick={() => setSelectedLineId(item.line_id)}>
            {item.line_id} · streak {item.correct_streak} · learned {item.learned} · needs_review {item.needs_review}
          </button>
        ))}
      </div>

      {items.length === 0 ? <p>No training lines available.</p> : null}

      <div style={{ marginTop: 10 }}>
        <button
          type="button"
          disabled={!canStart || sessionStart.isPending}
          onClick={() => activeLineId && sessionStart.mutate({ mode, line_id: activeLineId })}
        >
          Start session
        </button>
      </div>

      {activeSessionId ? (
        <div className="card" style={{ marginTop: 10 }}>
          <small>Session: {activeSessionId}</small>
          <div>
            <label>
              Attempt UCI
              <input
                value={attemptUci}
                onChange={(event) => setAttemptUci(event.target.value)}
                placeholder="e2e4"
              />
            </label>
            <button
              type="button"
              disabled={!attemptUci || answer.isPending}
              onClick={() => answer.mutate({ sessionId: activeSessionId, answerUci: attemptUci.trim() })}
            >
              Submit attempt
            </button>
          </div>
          {activeExpected ? <small>Next expected move: {activeExpected}</small> : null}
        </div>
      ) : null}

      {feedback ? <p>{feedback}</p> : null}
      {sessionStart.error || answer.error ? <p className="warn">Trainer session action failed.</p> : null}
    </div>
  );
}
