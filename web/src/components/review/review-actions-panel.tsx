"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { executeReviewAction, getReviewAction, listReviewActions, listReviewBranchQueue } from "@/lib/api-client";
import type { ReviewActionRequest, ReviewActionResponse } from "@/lib/types";

export function summarizeReviewActionResult(result: ReviewActionResponse): string {
  const statusBefore = result.status_change?.before ?? "unknown";
  const statusAfter = result.status_change?.after ?? "unknown";

  const queueBefore = result.queue_change?.before?.queue_status ?? "none";
  const queueAfter = result.queue_change?.after?.queue_status ?? "none";

  const priorityBefore = result.priority_change?.before;
  const priorityAfter = result.priority_change?.after;
  const prioritySegment =
    priorityBefore === null || priorityBefore === undefined || priorityAfter === null || priorityAfter === undefined
      ? "priority unchanged"
      : `priority ${priorityBefore}→${priorityAfter}`;

  const delta = result.queue_delta;
  const queueDeltaSegment = delta
    ? `queue Δ ${delta.before_queue_status ?? "none"}→${delta.after_queue_status ?? "none"} (added=${delta.added_to_queue}, removed=${delta.removed_from_queue})`
    : "queue Δ unavailable";

  return `Status ${statusBefore}→${statusAfter}; queue ${queueBefore}→${queueAfter}; ${prioritySegment}; ${queueDeltaSegment}.`;
}

export function buildQueueStatusMap(rows: { proposition_id: number; queue_status: string }[] | undefined): Map<number, string> {
  const map = new Map<number, string>();
  for (const row of rows ?? []) {
    map.set(row.proposition_id, row.queue_status);
  }
  return map;
}

export function deriveSelectedIdAfterAction(currentSelectedId: number | null, result: ReviewActionResponse): number | null {
  return result.proposition?.id ?? currentSelectedId;
}

interface ReviewActionsPanelProps {
  onActionCommitted?: () => Promise<void> | void;
}

export function ReviewActionsPanel({ onActionCommitted }: ReviewActionsPanelProps = {}) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<"pending" | "approved" | "disapproved" | "all">("pending");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [lastResult, setLastResult] = useState<ReviewActionResponse | null>(null);

  const actions = useQuery({ queryKey: ["review-actions", status], queryFn: () => listReviewActions(status) });
  const branchQueue = useQuery({ queryKey: ["review-branch-queue"], queryFn: listReviewBranchQueue });
  const detail = useQuery({
    queryKey: ["review-action-detail", selectedId],
    queryFn: () => getReviewAction(selectedId as number),
    enabled: selectedId !== null,
  });

  const mutate = useMutation({
    mutationFn: executeReviewAction,
    onSuccess: async (result) => {
      setLastResult(result);
      const nextSelectedId = deriveSelectedIdAfterAction(selectedId, result);
      setSelectedId(nextSelectedId);
      if (result.proposition) {
        queryClient.setQueryData(["review-action-detail", result.proposition.id], result.proposition);
      }
      if (onActionCommitted) {
        await onActionCommitted();
      } else {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["review-actions"] }),
          queryClient.invalidateQueries({ queryKey: ["review-branch-queue"] }),
        ]);
      }
    },
  });

  const queueCountByProposition = useMemo(() => buildQueueStatusMap(branchQueue.data), [branchQueue.data]);

  const submitAction = (payload: ReviewActionRequest) => {
    mutate.mutate(payload);
  };

  return (
    <div className="card">
      <h3>Review actions</h3>
      <label>
        Status
        <select value={status} onChange={(e) => setStatus(e.target.value as "pending" | "approved" | "disapproved" | "all")}>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="disapproved">Disapproved</option>
          <option value="all">All</option>
        </select>
      </label>
      <p>Items: {actions.data?.length ?? 0}</p>
      {(actions.data ?? []).slice(0, 8).map((item) => (
        <div key={item.id} className="card">
          <div>
            <button type="button" onClick={() => setSelectedId(item.id)}>
              #{item.id} {item.uci_move} ({item.status})
            </button>
          </div>
          <div>
            evidence {item.evidence_count}/{item.threshold_count} · queue {queueCountByProposition.get(item.id) ?? "none"}
          </div>
          <div>
            <button type="button" onClick={() => submitAction({ proposition_id: item.id, action: "done" })}>Done</button>
            <button type="button" onClick={() => submitAction({ proposition_id: item.id, action: "defer" })}>Defer</button>
            <button type="button" onClick={() => submitAction({ proposition_id: item.id, action: "priority" })}>Priority</button>
          </div>
        </div>
      ))}

      <div className="card">
        <h4>Evidence details</h4>
        {selectedId === null ? <p>Select a proposition to inspect evidence.</p> : null}
        {selectedId !== null && detail.isLoading ? <p>Loading proposition detail…</p> : null}
        {detail.data ? (
          <div>
            <p>
              #{detail.data.id} · {detail.data.uci_move} · status {detail.data.status}
            </p>
            <p>line hint: {detail.data.line_id_hint ?? "n/a"}</p>
            <pre>{JSON.stringify(detail.data.detail, null, 2)}</pre>
          </div>
        ) : null}
      </div>

      <div className="card">
        <h4>Latest action result</h4>
        {lastResult ? (
          <>
            <p>{summarizeReviewActionResult(lastResult)}</p>
            {lastResult.queue_delta ? (
              <p>
                Queue delta for #{lastResult.queue_delta.proposition_id}: {lastResult.queue_delta.before_queue_status ?? "none"} →{" "}
                {lastResult.queue_delta.after_queue_status ?? "none"}
              </p>
            ) : null}
          </>
        ) : (
          <p>No action taken in this session.</p>
        )}
      </div>

      {actions.error || mutate.error || detail.error || branchQueue.error ? <p className="warn">Review action request failed.</p> : null}
    </div>
  );
}
