"use client";

import { FormEvent, useEffect, useState } from "react";

import { PageContainer, PageSection } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SectionHeader } from "@/components/ui/section-header";
import { getRuntimeSettings, runFetchGames, updateRuntimeSettings } from "@/lib/api-client";

import { INITIAL_FORM, LABELS, SECTIONS, mapBackendFieldErrors, toList } from "./settings-form";

export default function SettingsPage() {
  const [form, setForm] = useState<Record<string, string>>(INITIAL_FORM);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");

  useEffect(() => {
    getRuntimeSettings().then((s) =>
      setForm((f) => ({
        ...f,
        daysBack: String(s.days_back),
        chesscomUsernames: s.chesscom_usernames.join(", "),
        lichessUsernames: s.lichess_usernames.join(", "),
        variants: s.variants.join(", "),
        gamesDir: s.games_dir ?? "",
        databasePath: s.database_path ?? "",
        repertoireDir: s.repertoire_dir ?? "",
        stockfishPath: s.stockfish_path ?? "",
        pieceDir: s.piece_dir ?? "",
        engineDepth: String(s.engine_depth ?? 20),
        maxPlies: String(s.max_plies ?? 30),
        engineThreads: String(s.engine_threads ?? 1),
        engineHashMb: String(s.engine_hash_mb ?? 0),
        engineMaxTimeMs: String(s.engine_max_time_ms ?? 300),
        engineWorkers: String(s.engine_workers ?? 0),
        engineWorkerCap: String(s.engine_worker_cap ?? 4),
        engineMode: s.engine_mode ?? "adaptive",
        engineProfile: s.engine_profile ?? "aggressive",
        enableEngineCache: String(Boolean(s.enable_engine_cache)),
        incrementalAnalysis: String(Boolean(s.incremental_analysis)),
        engineCachePruneNonActive: String(Boolean(s.engine_cache_prune_non_active)),
        reviewTopN: String(s.review_top_n ?? 25),
        tabiyaTopN: String(s.tabiya_top_n ?? 10),
        matchingMode: s.matching_mode ?? "STRICT",
        missingCoverageProposalThreshold: String(s.missing_coverage_proposal_threshold ?? 5),
        playerName: s.player_name ?? "",
        playerNames: s.player_names.join(", "),
        ratingBandSize: String(s.rating_band_size ?? 100),
      })),
    );
  }, []);

  async function onSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({});
    setMessage("");
    try {
      await updateRuntimeSettings({
        days_back: Number(form.daysBack),
        chesscom_usernames: toList(form.chesscomUsernames),
        lichess_usernames: toList(form.lichessUsernames),
        variants: toList(form.variants),
        games_dir: form.gamesDir,
        database_path: form.databasePath,
        repertoire_dir: form.repertoireDir,
        stockfish_path: form.stockfishPath,
        piece_dir: form.pieceDir,
        engine_depth: Number(form.engineDepth),
        max_plies: Number(form.maxPlies),
        engine_threads: Number(form.engineThreads),
        engine_hash_mb: Number(form.engineHashMb),
        engine_max_time_ms: Number(form.engineMaxTimeMs),
        engine_workers: Number(form.engineWorkers),
        engine_worker_cap: Number(form.engineWorkerCap),
        engine_mode: form.engineMode,
        engine_profile: form.engineProfile,
        enable_engine_cache: form.enableEngineCache === "true",
        incremental_analysis: form.incrementalAnalysis === "true",
        engine_cache_prune_non_active: form.engineCachePruneNonActive === "true",
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
    }
  }

  return (
    <PageContainer title="Settings" description="Manage runtime fetch, engine, path, and player profile configuration.">
      <PageSection>
        <SectionHeader title="Settings" description="Runtime configuration for fetching, engine behavior, and profile metadata." />
        <form onSubmit={onSave} className="grid gap-4">
          {SECTIONS.map((section) => (
            <Card key={section.title} className="grid gap-3 p-4">
              <h3 className="text-base font-semibold">{section.title}</h3>
              <div className="grid gap-3 md:grid-cols-2">
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
            <Button type="submit" variant="primary">
              Save settings
            </Button>
            <Button type="button" onClick={() => runFetchGames()}>
              Fetch games
            </Button>
          </div>
          {message ? <p className="text-sm text-text-subtle">{message}</p> : null}
        </form>
      </PageSection>
    </PageContainer>
  );
}
