"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getTrainerQueueV2, setTrainerPriorityOverride, submitTrainerOutcome } from "@/lib/api-client";

export function TrainerEndpointsPanel() {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"learn" | "review">("review");
  const [selectedLineId, setSelectedLineId] = useState<string | null>(null);
  const queue = useQuery({ queryKey: ["trainer", "queue-v2", mode], queryFn: () => getTrainerQueueV2(mode) });
  const items = useMemo(() => queue.data?.items ?? [], [queue.data]);
  const activeLineId = selectedLineId ?? items[0]?.line_id ?? null;
  const selectedItem = useMemo(() => items.find((item) => item.line_id === activeLineId) ?? null, [items, activeLineId]);
  const outcome = useMutation({ mutationFn: submitTrainerOutcome, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trainer", "queue-v2"] }) });
  const priority = useMutation({ mutationFn: setTrainerPriorityOverride, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trainer", "queue-v2"] }) });
  return (
    <Card className="xl:sticky xl:top-4 xl:self-start">
      <h3 className="text-base font-semibold">Trainer controls</h3>
      <div className="flex flex-wrap gap-2"><Button type="button" onClick={() => setMode("learn")}>Learn</Button><Button type="button" onClick={() => setMode("review")}>Review</Button></div>
      <p className="text-sm text-text-subtle">Queue items: {items.length}</p>
      <div className="grid gap-2">{items.slice(0, 8).map((item) => <Button key={item.line_id} type="button" variant="ghost" className="justify-start" onClick={() => setSelectedLineId(item.line_id)}>{item.line_id} · streak {item.correct_streak}</Button>)}</div>
      {selectedItem ? <><div className="flex flex-wrap gap-2"><Badge tone="accent">{selectedItem.line_id}</Badge><Badge>learned {String(selectedItem.learned)}</Badge><Badge>needs review {String(selectedItem.needs_review)}</Badge></div><div className="flex flex-wrap gap-2"><Button type="button" onClick={() => outcome.mutate({ line_id: selectedItem.line_id, is_correct: true, mode })}>✓ Correct</Button><Button type="button" onClick={() => outcome.mutate({ line_id: selectedItem.line_id, is_correct: false, mode })}>✗ Incorrect</Button><Button type="button" onClick={() => priority.mutate({ line_id: selectedItem.line_id, value: 1 })}>★ Priority</Button></div></> : <small className="text-text-muted">No selectable line in queue.</small>}
      {outcome.error || priority.error || queue.error ? <p className="text-sm text-danger">Trainer endpoint action failed.</p> : null}
      <Card className="border-border/80 bg-panel-muted"><strong>Remediation visibility</strong><p className="text-sm text-text-subtle">Incorrect session answers must include remediation with fields: <code>best_move_uci</code>, <code>principal_variation[]</code>, <code>explanation_markdown</code>, and <code>retry_required</code>.</p></Card>
    </Card>
  );
}
