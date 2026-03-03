"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { executeReviewAction, listReviewActions } from "@/lib/api-client";

export function ReviewActionsPanel() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<"pending" | "approved" | "disapproved" | "all">("pending");

  const actions = useQuery({ queryKey: ["review-actions", status], queryFn: () => listReviewActions(status) });
  const mutate = useMutation({
    mutationFn: executeReviewAction,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["review-actions"] }),
  });

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
          <div>#{item.id} {item.uci_move} ({item.status})</div>
          <div>
            <button type="button" onClick={() => mutate.mutate({ proposition_id: item.id, action: "done" })}>Done</button>
            <button type="button" onClick={() => mutate.mutate({ proposition_id: item.id, action: "defer" })}>Defer</button>
            <button type="button" onClick={() => mutate.mutate({ proposition_id: item.id, action: "priority" })}>Priority</button>
          </div>
        </div>
      ))}
      {actions.error || mutate.error ? <p className="warn">Review action request failed.</p> : null}
    </div>
  );
}
