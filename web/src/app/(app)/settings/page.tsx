"use client";

import { FormEvent, useEffect, useState } from "react";

import { PageContainer, PageSection } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SectionHeader } from "@/components/ui/section-header";
import { getRuntimeSettings, runFetchGames, updateRuntimeSettings } from "@/lib/api-client";

const INITIAL_FORM: Record<string, string> = {
  daysBack: "180",
  chesscomUsernames: "",
  lichessUsernames: "",
  variants: "",
  gamesDir: "",
  databasePath: "",
  repertoireDir: "",
  stockfishPath: "",
  pieceDir: "",
  engineDepth: "20",
  maxPlies: "30",
  engineThreads: "1",
  engineHashMb: "0",
  engineMaxTimeMs: "300",
  playerName: "",
  playerNames: "",
};

export const SECTIONS = [
  { title: "Paths", fields: ["gamesDir", "databasePath", "repertoireDir", "stockfishPath", "pieceDir"] as const },
  { title: "Engine", fields: ["engineDepth", "maxPlies", "engineThreads", "engineHashMb", "engineMaxTimeMs"] as const },
  { title: "Profile", fields: ["playerName", "playerNames"] as const },
  { title: "Fetch", fields: ["chesscomUsernames", "lichessUsernames", "variants", "daysBack"] as const },
] as const;

const LABELS: Record<string, string> = {
  daysBack: "Days back",
  chesscomUsernames: "Chess.com usernames",
  lichessUsernames: "Lichess usernames",
  variants: "Variants",
  gamesDir: "Games directory",
  databasePath: "Database path",
  repertoireDir: "Repertoire directory",
  stockfishPath: "Stockfish path",
  pieceDir: "Piece directory",
  engineDepth: "Engine depth",
  maxPlies: "Max plies",
  engineThreads: "Engine threads",
  engineHashMb: "Engine hash MB",
  engineMaxTimeMs: "Engine max time (ms)",
  playerName: "Player name",
  playerNames: "Player aliases",
};

const BACKEND_TO_FORM_FIELD: Record<string, string> = {
  days_back: "daysBack",
  chesscom_usernames: "chesscomUsernames",
  lichess_usernames: "lichessUsernames",
  variants: "variants",
  games_dir: "gamesDir",
  database_path: "databasePath",
  repertoire_dir: "repertoireDir",
  stockfish_path: "stockfishPath",
  piece_dir: "pieceDir",
  engine_depth: "engineDepth",
  max_plies: "maxPlies",
  engine_threads: "engineThreads",
  engine_hash_mb: "engineHashMb",
  engine_max_time_ms: "engineMaxTimeMs",
  player_name: "playerName",
  player_names: "playerNames",
};

function toList(value: string): string[] {
  return value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

export function mapBackendFieldErrors(raw: string): Record<string, string> {
  try {
    const parsed = JSON.parse(raw) as { detail?: Array<{ field?: string; code?: string; message?: string }> };
    const mapped: Record<string, string> = {};
    for (const item of parsed.detail ?? []) {
      const key = BACKEND_TO_FORM_FIELD[item.field ?? ""];
      if (!key) continue;
      mapped[key] = item.message || item.code || "Invalid value";
    }
    return mapped;
  } catch {
    return {};
  }
}

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
        playerName: s.player_name ?? "",
        playerNames: s.player_names.join(", "),
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
        player_name: form.playerName,
        player_names: toList(form.playerNames),
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
