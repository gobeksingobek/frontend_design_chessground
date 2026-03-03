"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ChessBoard } from "@/components/chess/chess-board";
import { getTrainerQueue, submitTrainerAnswer } from "@/lib/api-client";
import type { TrainerAnswerResult } from "@/lib/types";

export function TrainerQueue() {
  const queryClient = useQueryClient();
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [lastResult, setLastResult] = useState<TrainerAnswerResult | null>(null);
  const [sessionScore, setSessionScore] = useState(0);

  const { data, isLoading, error } = useQuery({
    queryKey: ["trainer", "queue"],
    queryFn: getTrainerQueue,
  });

  const queue = data?.items ?? [];
  const currentItem = queue[index] ?? null;

  const answerMutation = useMutation({
    mutationFn: submitTrainerAnswer,
    onSuccess: (result) => {
      setLastResult(result);
      setAnswer("");
      setSessionScore((current) => current + result.score_delta);
      setIndex((current) => current + 1);
      queryClient.invalidateQueries({ queryKey: ["trainer", "queue"] });
    },
  });

  if (isLoading) return <p>Loading trainer queue...</p>;
  if (error) return <p className="warn">Failed to load trainer queue: {(error as Error).message}</p>;
  if (queue.length === 0) return <p>No training positions due. Check back after more games or analysis jobs.</p>;

  return (
    <div className="split-layout">
      <div className="card">
        <h3>Next position</h3>
        {currentItem ? (
          <>
            <ChessBoard fen={currentItem.fen} title={currentItem.line_label ?? "Trainer position"} />
            <p>{currentItem.prompt}</p>
            <p>
              Queue position <strong>{Math.min(index + 1, queue.length)}</strong> / <strong>{queue.length}</strong>
            </p>
          </>
        ) : (
          <p>Queue complete for now. Great work.</p>
        )}
      </div>

      <div className="card">
        <h3>Review flow</h3>
        <label>
          Your move (UCI)
          <input
            value={answer}
            onChange={(event) => setAnswer(event.target.value)}
            placeholder="e2e4"
            disabled={!currentItem || answerMutation.isPending}
          />
        </label>
        <button
          type="button"
          disabled={!currentItem || !answer.trim() || answerMutation.isPending}
          onClick={() => {
            if (!currentItem) return;
            answerMutation.mutate({ item_id: currentItem.id, answer_uci: answer.trim().toLowerCase() });
          }}
        >
          {answerMutation.isPending ? "Checking..." : "Submit answer"}
        </button>

        {answerMutation.error ? <p className="warn">{(answerMutation.error as Error).message}</p> : null}

        {lastResult ? (
          <div className="card">
            <h4>Result</h4>
            <p className={lastResult.is_correct ? "ok" : "warn"}>{lastResult.message}</p>
            <p>Correct move: {lastResult.correct_uci ?? "n/a"}</p>
            <p>Score delta: {lastResult.score_delta}</p>
          </div>
        ) : (
          <small>Submit an answer to see scoring and feedback.</small>
        )}

        <p>
          Session score: <strong>{sessionScore}</strong>
        </p>
      </div>
    </div>
  );
}
