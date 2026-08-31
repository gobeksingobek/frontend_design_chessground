"use client";

import { FormEvent, useEffect, useState } from "react";

import { PageContainer, PageSection } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SectionHeader } from "@/components/ui/section-header";
import { Skeleton } from "@/components/ui/skeleton";
import { getRuntimeSettings, runFetchGames, updateRuntimeSettings } from "@/lib/api-client";
import { cn } from "@/lib/cn";

import { INITIAL_FORM, LABELS, SECTIONS, mapBackendFieldErrors, toList } from "./settings-form";

export default function SettingsPage() {
  const [form, setForm] = useState<Record<string, string>>(INITIAL_FORM);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    getRuntimeSettings().then((s) => {
      setForm((f) => ({
        ...f,
        daysBack: String(s.days_back),
        chesscomUsernames: s.chesscom_usernames.join(", "),
        lichessUsernames: s.lichess_usernames.join(", "),
        variants: s.variants.join(", "),
        engineDepth: String(s.engine_depth ?? 20),
        maxPlies: String(s.max_plies ?? 30),
        enableEngineCache: String(Boolean(s.enable_engine_cache)),
        incrementalAnalysis: String(Boolean(s.incremental_analysis)),
        reviewTopN: String(s.review_top_n ?? 25),
        tabiyaTopN: String(s.tabiya_top_n ?? 10),
        matchingMode: s.matching_mode ?? "STRICT",
        missingCoverageProposalThreshold: String(s.missing_coverage_proposal_threshold ?? 5),
        playerName: s.player_name ?? "",
        playerNames: s.player_names.join(", "),
        ratingBandSize: String(s.rating_band_size ?? 100),
      }));
    }).catch((error) => {
      setMessage(error instanceof Error ? error.message : "Unable to load settings.");
    }).finally(() => setIsLoading(false));
  }, []);

  async function onSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({});
    setMessage("");
    setIsSaving(true);
    try {
      await updateRuntimeSettings({
        days_back: Number(form.daysBack),
        chesscom_usernames: toList(form.chesscomUsernames),
        lichess_usernames: toList(form.lichessUsernames),
        variants: toList(form.variants),
        engine_depth: Number(form.engineDepth),
        max_plies: Number(form.maxPlies),
        enable_engine_cache: form.enableEngineCache === "true",
        incremental_analysis: form.incrementalAnalysis === "true",
        review_top_n: Number(form.reviewTopN),
        tabiya_top_n: Number(form.tabiyaTopN),
        matching_mode: form.matchingMode,
        missing_coverage_proposal_threshold: Number(form.missingCoverageProposalThreshold),
        player_name: form.playerName,
        player_names: toList(form.playerNames),
        rating_band_size: Number(form.ratingBandSize),
      });
      setMessage("Settings saved.");
    } catch (err) {
      const mapped = mapBackendFieldErrors((err as Error).message);
      if (Object.keys(mapped).length > 0) {
        setErrors(mapped);
      } else {
        setMessage((err as Error).message);
      }
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <PageContainer title="Settings" description="Manage workspace analysis, fetch, and player profile configuration.">
      <PageSection>
        <SectionHeader title="Settings" description="Workspace settings are stored by the backend and shared by every client." />
        {isLoading ? <div className="grid gap-4"><Skeleton className="h-44 rounded-card" /><Skeleton className="h-44 rounded-card" /></div> : <form onSubmit={onSave} className="grid gap-4">
          {SECTIONS.map((section) => (
            <Card key={section.title} className="grid gap-4">
              <div className="border-b border-border/35 pb-3"><h3 className="text-base font-semibold tracking-tight">{section.title}</h3></div>
              <div className="grid gap-4 md:grid-cols-2">
                {section.fields.map((fieldKey) => (
                  <label key={fieldKey} className="grid gap-2 text-sm text-text-subtle">
                    {LABELS[fieldKey] ?? fieldKey}
                    <Input value={form[fieldKey] ?? ""} onChange={(e) => setForm({ ...form, [fieldKey]: e.target.value })} />
                    {errors[fieldKey] ? <small className="text-danger">{errors[fieldKey]}</small> : null}
                  </label>
                ))}
              </div>
            </Card>
          ))}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant="primary" disabled={isSaving}>
              {isSaving ? "Saving…" : "Save settings"}
            </Button>
            <Button type="button" onClick={() => runFetchGames()}>
              Fetch games
            </Button>
          </div>
          {message ? <p className={cn("rounded-control border px-4 py-3 text-sm", message === "Settings saved." ? "border-success/25 bg-success/10 text-success" : "border-warning/25 bg-warning/10 text-warning")}>{message}</p> : null}
        </form>}
      </PageSection>
    </PageContainer>
  );
}
