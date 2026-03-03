"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getTrainerQueueV2, submitTrainerOutcome } from "@/lib/api-client";

export function TrainerQueue() {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"learn" | "review">("review");

  const { data, isLoading, error } = useQuery({
    queryKey: ["trainer", "queue-list", mode],
    queryFn: () => getTrainerQueueV2(mode),
  });

  const outcome = useMutation({
    mutationFn: submitTrainerOutcome,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trainer", "queue-list"] }),
  });

  if (isLoading) return <p>Loading trainer queue...</p>;
  if (error) return <p className="warn">Failed to load trainer queue: {(error as Error).message}</p>;

  const items = data?.items ?? [];

  return (
    <div className="card">
      <h3>Trainer queue rows</h3>
      <label>
        Mode
        <select value={mode} onChange={(event) => setMode(event.target.value as "learn" | "review") }>
          <option value="learn">Learn</option>
          <option value="review">Review</option>
        </select>
      </label>
      {items.length === 0 ? <p>No training lines available.</p> : null}
      {items.map((item) => (
        <div key={item.line_id} className="card">
          <div>{item.line_id}</div>
          <small>
            streak {item.correct_streak} · learned {item.learned} · needs_review {item.needs_review} · auto {item.auto_priority_score}
          </small>
          <div>
            <button type="button" onClick={() => outcome.mutate({ line_id: item.line_id, is_correct: true, mode })}>Correct</button>
            <button type="button" onClick={() => outcome.mutate({ line_id: item.line_id, is_correct: false, mode })}>Incorrect</button>
          </div>
        </div>
      ))}
      {outcome.error ? <p className="warn">Failed to record outcome.</p> : null}
    </div>
  );
}
