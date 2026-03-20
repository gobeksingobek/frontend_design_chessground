"use client";

import { useState } from "react";

import { PageContainer, PageSection } from "@/components/app-shell";
import { ChessBoard } from "@/components/chess/chess-board";
import { TrainerEndpointsPanel } from "@/components/trainer/trainer-endpoints-panel";
import { TrainerQueue } from "@/components/trainer/trainer-queue";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SectionHeader } from "@/components/ui/section-header";
import { Select } from "@/components/ui/select";
import { createTrainerSession, submitTrainerSessionAnswer } from "@/lib/api-client";
import type { TrainerSessionItem } from "@/lib/types";

export default function TrainerPage() {
  const [mode, setMode] = useState<"learn" | "review">("review");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [item, setItem] = useState<TrainerSessionItem | null>(null);
  const [statusText, setStatusText] = useState<string | null>(null);
  const createOrResumeSession = async () => { const response = await createTrainerSession({ mode }); setSessionId(response.session_id); setItem(response.item); setStatusText(`Session started. Queue snapshot: remaining ${response.queue_snapshot.remaining}, learned ${response.queue_snapshot.learned}, needs_review ${response.queue_snapshot.needs_review}`); };
  const endSession = () => { setSessionId(null); setItem(null); setStatusText("Session ended."); };
  return (
    <PageContainer title="Trainer" description="Start learning or review sessions, work through the queue, and capture outcomes.">
      <PageSection>
        <SectionHeader title="Trainer" description="Queue positions, record outcomes, and apply priority overrides." />
        <label className="grid max-w-xs gap-2 rounded-2xl border border-border bg-panel px-4 py-4 text-sm text-text-subtle shadow-soft">Mode<Select value={mode} onChange={(event) => setMode(event.target.value as "learn" | "review")}><option value="learn">Learn</option><option value="review">Review</option></Select></label>
        <div className="grid gap-4 xl:grid-cols-board">
          <Card><ChessBoard size="large" title="Training board" /><div className="mt-3 flex flex-wrap gap-2"><Button type="button" variant="primary" onClick={createOrResumeSession}>{sessionId ? "Resume / Restart session" : "Create / Start session"}</Button><Button type="button" onClick={endSession} disabled={!sessionId}>End session</Button></div></Card>
          <div className="grid gap-4"><TrainerEndpointsPanel /><TrainerQueue mode={mode} sessionId={sessionId} item={item} statusText={statusText} onStart={createOrResumeSession} onAnswer={async (moveUci, elapsedMs) => { if (!sessionId) throw new Error("No active session"); const response = await submitTrainerSessionAnswer(sessionId, { move_uci: moveUci, elapsed_ms: elapsedMs }); setItem(response.next_item ?? null); setStatusText(`Outcome ${response.outcome}, grade ${response.grade}, streak_delta ${response.streak_delta}.`); return response; }} onNext={() => { if (!item) endSession(); }} /></div>
        </div>
      </PageSection>
    </PageContainer>
  );
}
