"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getTrainerQueueV2, setTrainerPriorityOverride, submitTrainerOutcome } from "@/lib/api-client";

export function TrainerEndpointsPanel() {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"learn" | "review">("review");
  const [selectedLineId, setSelectedLineId] = useState<string | null>(null);

  const queue = useQuery({ queryKey: ["trainer", "queue-v2", mode], queryFn: () => getTrainerQueueV2(mode) });

  const items = useMemo(() => queue.data?.items ?? [], [queue.data]);
  const activeLineId = selectedLineId ?? items[0]?.line_id ?? null;
  const selectedItem = useMemo(() => items.find((item) => item.line_id === activeLineId) ?? null, [items, activeLineId]);

  const outcome = useMutation({
    mutationFn: submitTrainerOutcome,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trainer", "queue-v2"] }),
  });
  const priority = useMutation({
    mutationFn: setTrainerPriorityOverride,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trainer", "queue-v2"] }),
  });

  return (
    <div className="card menu-card">
      <h3>Trainer controls</h3>
      <div className="board-controls">
        <button type="button" onClick={() => setMode("learn")}>Learn</button>
        <button type="button" onClick={() => setMode("review")}>Review</button>
      </div>
      <p>Queue items: {items.length}</p>
      <div className="stack">
        {items.slice(0, 8).map((item) => (
          <button key={item.line_id} type="button" onClick={() => setSelectedLineId(item.line_id)}>
            {item.line_id} · streak {item.correct_streak}
          </button>
        ))}
      </div>
      {selectedItem ? (
        <>
          <small>
            {selectedItem.line_id} · learned {selectedItem.learned} · needs review {selectedItem.needs_review}
          </small>
          <div className="board-controls">
            <button type="button" onClick={() => outcome.mutate({ line_id: selectedItem.line_id, is_correct: true, mode })}>✓ Correct</button>
            <button type="button" onClick={() => outcome.mutate({ line_id: selectedItem.line_id, is_correct: false, mode })}>✗ Incorrect</button>
            <button type="button" onClick={() => priority.mutate({ line_id: selectedItem.line_id, value: 1 })}>★ Priority</button>
          </div>
        </>
      ) : (
        <small>No selectable line in queue.</small>
      )}
      {outcome.error || priority.error || queue.error ? <p className="warn">Trainer endpoint action failed.</p> : null}
      <div className="card" style={{ marginTop: 10 }}>
        <strong>Remediation visibility</strong>
        <p>
          Incorrect session answers must include remediation with fields:
          <code> best_move_uci</code>,
          <code> principal_variation[]</code>,
          <code> explanation_markdown</code>, and
          <code> retry_required</code>.
        </p>
      </div>
    </div>
  );
}
