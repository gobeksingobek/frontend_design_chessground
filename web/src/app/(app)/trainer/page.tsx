"use client";

import { useState } from "react";

import { ChessBoard } from "@/components/chess/chess-board";
import { TrainerEndpointsPanel } from "@/components/trainer/trainer-endpoints-panel";
import { TrainerQueue } from "@/components/trainer/trainer-queue";
import { createTrainerSession, submitTrainerSessionAnswer } from "@/lib/api-client";
import type { TrainerSessionItem } from "@/lib/types";

export default function TrainerPage() {
  const [mode, setMode] = useState<"learn" | "review">("review");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [item, setItem] = useState<TrainerSessionItem | null>(null);
  const [statusText, setStatusText] = useState<string | null>(null);

  const createOrResumeSession = async () => {
    const response = await createTrainerSession({ mode });
    setSessionId(response.session_id);
    setItem(response.item);
    setStatusText(
      `Session started. Queue snapshot: remaining ${response.queue_snapshot.remaining}, learned ${response.queue_snapshot.learned}, needs_review ${response.queue_snapshot.needs_review}`,
    );
  };

  const endSession = () => {
    setSessionId(null);
    setItem(null);
    setStatusText("Session ended.");
  };

  return (
    <div className="stack">
      <h2>Trainer</h2>
      <p>Queue positions, record outcomes, and apply priority overrides.</p>
      <label>
        Mode
        <select value={mode} onChange={(event) => setMode(event.target.value as "learn" | "review")}>
          <option value="learn">Learn</option>
          <option value="review">Review</option>
        </select>
      </label>
      <div className="board-page-layout">
        <div className="card">
          <ChessBoard size="large" title="Training board" />
          <div className="stack" style={{ marginTop: 10 }}>
            <button type="button" onClick={createOrResumeSession}>
              {sessionId ? "Resume / Restart session" : "Create / Start session"}
            </button>
            <button type="button" onClick={endSession} disabled={!sessionId}>
              End session
            </button>
          </div>
        </div>
        <div className="stack">
          <TrainerEndpointsPanel />
          <TrainerQueue
            mode={mode}
            sessionId={sessionId}
            item={item}
            statusText={statusText}
            onStart={createOrResumeSession}
            onAnswer={async (moveUci, elapsedMs) => {
              if (!sessionId) {
                throw new Error("No active session");
              }
              const response = await submitTrainerSessionAnswer(sessionId, { move_uci: moveUci, elapsed_ms: elapsedMs });
              setItem(response.next_item ?? null);
              setStatusText(`Outcome ${response.outcome}, grade ${response.grade}, streak_delta ${response.streak_delta}.`);
              return response;
            }}
            onNext={() => {
              if (!item) {
                endSession();
              }
            }}
          />
        </div>
      </div>
    </div>
  );
}
