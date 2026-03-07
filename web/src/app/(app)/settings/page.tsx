"use client";

import { FormEvent, useEffect, useState } from "react";

import { getRuntimeSettings, runFetchGames, updateRuntimeSettings } from "@/lib/api-client";

function toList(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

export default function SettingsPage() {
  const [form, setForm] = useState<Record<string, string>>({
    chesscomUsernames: "",
    lichessUsernames: "",
    variants: "",
    daysBack: "180",
    repertoireDir: "",
    gamesDir: "",
    databasePath: "",
    stockfishPath: "",
    pieceDir: "",
    engineDepth: "20",
    maxPlies: "30",
    playerName: "",
    playerNames: "",
    ratingBandSize: "100",
    matchingMode: "STRICT",
    reviewTopN: "25",
    tabiyaTopN: "10",
    engineWorkers: "0",
    engineWorkerCap: "4",
    engineThreads: "1",
    engineHashMb: "0",
    engineMode: "adaptive",
    engineMaxTimeMs: "300",
    engineProfile: "aggressive",
    missingCoverageProposalThreshold: "5",
  });
  const [bools, setBools] = useState({ enableEngineCache: true, incrementalAnalysis: true, engineCachePruneNonActive: true });

  const [loadState, setLoadState] = useState<"idle" | "loading" | "error">("idle");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [fetchState, setFetchState] = useState<"idle" | "running" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let mounted = true;
    setLoadState("loading");
    getRuntimeSettings().then((settings) => {
      if (!mounted) return;
      setForm((prev) => ({
        ...prev,
        chesscomUsernames: settings.chesscom_usernames.join(", "),
        lichessUsernames: settings.lichess_usernames.join(", "),
        variants: settings.variants.join(", "),
        daysBack: String(settings.days_back),
        repertoireDir: settings.repertoire_dir ?? "",
        gamesDir: settings.games_dir ?? "",
        databasePath: settings.database_path ?? "",
        stockfishPath: settings.stockfish_path ?? "",
        pieceDir: settings.piece_dir ?? "",
        engineDepth: String(settings.engine_depth ?? 20),
        maxPlies: String(settings.max_plies ?? 30),
        playerName: settings.player_name ?? "",
        playerNames: settings.player_names.join(", "),
        ratingBandSize: String(settings.rating_band_size ?? 100),
        matchingMode: settings.matching_mode ?? "STRICT",
        reviewTopN: String(settings.review_top_n ?? 25),
        tabiyaTopN: String(settings.tabiya_top_n ?? 10),
        engineWorkers: String(settings.engine_workers ?? 0),
        engineWorkerCap: String(settings.engine_worker_cap ?? 4),
        engineThreads: String(settings.engine_threads ?? 1),
        engineHashMb: String(settings.engine_hash_mb ?? 0),
        engineMode: settings.engine_mode ?? "adaptive",
        engineMaxTimeMs: String(settings.engine_max_time_ms ?? 300),
        engineProfile: settings.engine_profile ?? "aggressive",
        missingCoverageProposalThreshold: String(settings.missing_coverage_proposal_threshold ?? 5),
      }));
      setBools({
        enableEngineCache: Boolean(settings.enable_engine_cache ?? true),
        incrementalAnalysis: Boolean(settings.incremental_analysis ?? true),
        engineCachePruneNonActive: Boolean(settings.engine_cache_prune_non_active ?? true),
      });
      setLoadState("idle");
    }).catch((err) => {
      if (!mounted) return;
      setLoadState("error");
      setMessage((err as Error).message);
    });

    return () => { mounted = false; };
  }, []);

  async function onSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaveState("saving");
    setMessage("");

    const parsedDaysBack = Number(form.daysBack);
    if (!Number.isInteger(parsedDaysBack) || parsedDaysBack < 1) {
      setSaveState("error");
      setMessage("Days back must be a positive integer.");
      return;
    }

    try {
      await updateRuntimeSettings({
        chesscom_usernames: toList(form.chesscomUsernames),
        lichess_usernames: toList(form.lichessUsernames),
        variants: toList(form.variants),
        days_back: parsedDaysBack,
        repertoire_dir: form.repertoireDir,
        games_dir: form.gamesDir,
        database_path: form.databasePath,
        stockfish_path: form.stockfishPath,
        piece_dir: form.pieceDir,
        engine_depth: Number(form.engineDepth),
        max_plies: Number(form.maxPlies),
        player_name: form.playerName,
        player_names: toList(form.playerNames),
        rating_band_size: Number(form.ratingBandSize),
        matching_mode: form.matchingMode,
        enable_engine_cache: bools.enableEngineCache,
        incremental_analysis: bools.incrementalAnalysis,
        review_top_n: Number(form.reviewTopN),
        tabiya_top_n: Number(form.tabiyaTopN),
        engine_workers: Number(form.engineWorkers),
        engine_worker_cap: Number(form.engineWorkerCap),
        engine_threads: Number(form.engineThreads),
        engine_hash_mb: Number(form.engineHashMb),
        engine_mode: form.engineMode,
        engine_max_time_ms: Number(form.engineMaxTimeMs),
        engine_profile: form.engineProfile,
        engine_cache_prune_non_active: bools.engineCachePruneNonActive,
        missing_coverage_proposal_threshold: Number(form.missingCoverageProposalThreshold),
      });
      setSaveState("success");
      setMessage("Settings saved.");
    } catch (err) {
      setSaveState("error");
      setMessage((err as Error).message);
    }
  }

  async function onFetchGames() {
    setFetchState("running");
    setMessage("");
    try {
      const result = await runFetchGames();
      setFetchState("success");
      setMessage(`Started fetch-games (${result.job_id.slice(0, 8)}…).`);
    } catch (err) {
      setFetchState("error");
      setMessage((err as Error).message);
    }
  }

  return (
    <div className="stack">
      <h2>Settings</h2>
      {loadState === "loading" ? <p>Loading runtime settings…</p> : null}
      {loadState === "error" ? <p className="warn">{message}</p> : null}

      <form className="card stack" onSubmit={onSave}>
        {Object.entries(form).map(([key, value]) => (
          <label className="stack" key={key}>
            <span>{key}</span>
            <input value={value} onChange={(event) => setForm((prev) => ({ ...prev, [key]: event.target.value }))} />
          </label>
        ))}

        <label><input type="checkbox" checked={bools.enableEngineCache} onChange={(e) => setBools((b) => ({ ...b, enableEngineCache: e.target.checked }))} /> enableEngineCache</label>
        <label><input type="checkbox" checked={bools.incrementalAnalysis} onChange={(e) => setBools((b) => ({ ...b, incrementalAnalysis: e.target.checked }))} /> incrementalAnalysis</label>
        <label><input type="checkbox" checked={bools.engineCachePruneNonActive} onChange={(e) => setBools((b) => ({ ...b, engineCachePruneNonActive: e.target.checked }))} /> engineCachePruneNonActive</label>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button type="submit" disabled={saveState === "saving" || loadState === "loading"}>Save settings</button>
          <button type="button" disabled={fetchState === "running"} onClick={onFetchGames}>Fetch games</button>
        </div>

        {message ? <p className={saveState === "error" || fetchState === "error" ? "warn" : "ok"}>{message}</p> : null}
      </form>
    </div>
  );
}
