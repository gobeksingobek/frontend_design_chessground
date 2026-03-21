"use client";

import { useState } from "react";

import { PageContainer, PageSection } from "@/components/app-shell";
import { ChessBoard } from "@/components/chess/chess-board";
import { TrainerEndpointsPanel } from "@/components/trainer/trainer-endpoints-panel";
import { TrainerQueue } from "@/components/trainer/trainer-queue";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FormField } from "@/components/ui/form-field";
import { SectionHeader } from "@/components/ui/section-header";
import { Select } from "@/components/ui/select";
import { StatCard } from "@/components/ui/stat-card";
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
        <div className="grid gap-4 xl:grid-cols-board">
          <Card className="gap-4">
            <FormField label="Mode" helpText="Learn introduces new material. Review revisits lines already in the spaced-repetition queue." className="max-w-xs">
              <Select value={mode} onChange={(event) => setMode(event.target.value as "learn" | "review")}>
                <option value="learn">Learn</option>
                <option value="review">Review</option>
              </Select>
            </FormField>
            <ChessBoard size="large" title="Training board" subtitle="Responsive board chrome stays balanced while you work through queued positions." />
            <div className="grid gap-3 md:grid-cols-2">
              <StatCard label="Session" value={sessionId ? "Active" : "Idle"} detail={sessionId ? `Session id ${sessionId}` : "Start a trainer run to receive the next queued position."} />
              <StatCard label="Current item" value={item?.branch_id ?? "None"} detail={statusText ?? "No queue updates yet."} />
            </div>
            <div className="mt-1 flex flex-wrap gap-2"><Button type="button" size="lg" variant="primary" onClick={createOrResumeSession}>{sessionId ? "Resume / restart session" : "Create / start session"}</Button><Button type="button" variant="ghost" onClick={endSession} disabled={!sessionId}>End session</Button></div>
          </Card>
          <div className="grid gap-4"><TrainerEndpointsPanel /><TrainerQueue mode={mode} sessionId={sessionId} item={item} statusText={statusText} onStart={createOrResumeSession} onAnswer={async (moveUci, elapsedMs) => { if (!sessionId) throw new Error("No active session"); const response = await submitTrainerSessionAnswer(sessionId, { move_uci: moveUci, elapsed_ms: elapsedMs }); setItem(response.next_item ?? null); setStatusText(`Outcome ${response.outcome}, grade ${response.grade}, streak_delta ${response.streak_delta}.`); return response; }} onNext={() => { if (!item) endSession(); }} /></div>
        </div>
      </PageSection>
    </PageContainer>
  );
}
