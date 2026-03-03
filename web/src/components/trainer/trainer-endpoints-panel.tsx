"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getTrainerQueueV2, setTrainerPriorityOverride, submitTrainerOutcome } from "@/lib/api-client";

export function TrainerEndpointsPanel() {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"learn" | "review">("review");
  const [lineId, setLineId] = useState("");

  const queue = useQuery({ queryKey: ["trainer", "queue-v2", mode], queryFn: () => getTrainerQueueV2(mode) });

  const outcome = useMutation({
    mutationFn: submitTrainerOutcome,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trainer", "queue-v2"] }),
  });
  const priority = useMutation({
    mutationFn: setTrainerPriorityOverride,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trainer", "queue-v2"] }),
  });

  const firstLineId = queue.data?.items[0]?.line_id ?? "";

  return (
    <div className="card">
      <h3>Trainer endpoint controls</h3>
      <label>
        Mode
        <select value={mode} onChange={(e) => setMode(e.target.value as "learn" | "review")}>
          <option value="learn">Learn</option>
          <option value="review">Review</option>
        </select>
      </label>
      <p>Queue items: {queue.data?.items.length ?? 0}</p>
      <label>
        Line ID
        <input value={lineId} onChange={(e) => setLineId(e.target.value)} placeholder={firstLineId || "line id"} />
      </label>
      <div>
        <button type="button" onClick={() => outcome.mutate({ line_id: lineId || firstLineId, is_correct: true, mode })}>Mark Correct</button>
        <button type="button" onClick={() => outcome.mutate({ line_id: lineId || firstLineId, is_correct: false, mode })}>Mark Incorrect</button>
        <button type="button" onClick={() => priority.mutate({ line_id: lineId || firstLineId, value: 1 })}>Priority On</button>
      </div>
      {outcome.error || priority.error || queue.error ? <p className="warn">Trainer endpoint action failed.</p> : null}
    </div>
  );
}
