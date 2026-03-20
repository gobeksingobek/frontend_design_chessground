"use client";

import { FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SectionHeader } from "@/components/ui/section-header";
import { getRuntimeSettings, runFetchGames, updateRuntimeSettings } from "@/lib/api-client";

function toList(value: string): string[] { return value.split(",").map((v) => v.trim()).filter(Boolean); }
const SECTIONS = { Fetch: ["chesscomUsernames", "lichessUsernames", "variants", "daysBack"], Paths: ["gamesDir", "databasePath", "repertoireDir", "stockfishPath", "pieceDir"], Engine: ["engineDepth", "engineThreads", "engineHashMb", "engineMaxTimeMs"], Profile: ["playerName", "playerNames"] } as const;

export default function SettingsPage() {
  const [form, setForm] = useState<Record<string, string>>({ daysBack: "180", chesscomUsernames: "", lichessUsernames: "", variants: "", gamesDir: "", databasePath: "", repertoireDir: "", stockfishPath: "", pieceDir: "", engineDepth: "20", engineThreads: "1", engineHashMb: "0", engineMaxTimeMs: "300", playerName: "", playerNames: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  useEffect(() => { getRuntimeSettings().then((s) => setForm((f) => ({ ...f, daysBack: String(s.days_back), chesscomUsernames: s.chesscom_usernames.join(", "), lichessUsernames: s.lichess_usernames.join(", "), variants: s.variants.join(", "), gamesDir: s.games_dir ?? "", databasePath: s.database_path ?? "", repertoireDir: s.repertoire_dir ?? "", stockfishPath: s.stockfish_path ?? "", pieceDir: s.piece_dir ?? "", engineDepth: String(s.engine_depth ?? 20), engineThreads: String(s.engine_threads ?? 1), engineHashMb: String(s.engine_hash_mb ?? 0), engineMaxTimeMs: String(s.engine_max_time_ms ?? 300), playerName: s.player_name ?? "", playerNames: s.player_names.join(", ") }))); }, []);
  async function onSave(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setErrors({}); try { await updateRuntimeSettings({ days_back: Number(form.daysBack), chesscom_usernames: toList(form.chesscomUsernames), lichess_usernames: toList(form.lichessUsernames), variants: toList(form.variants), games_dir: form.gamesDir, database_path: form.databasePath, repertoire_dir: form.repertoireDir, stockfish_path: form.stockfishPath, piece_dir: form.pieceDir, engine_depth: Number(form.engineDepth), engine_threads: Number(form.engineThreads), engine_hash_mb: Number(form.engineHashMb), engine_max_time_ms: Number(form.engineMaxTimeMs), player_name: form.playerName, player_names: toList(form.playerNames) }); setMessage("Settings saved."); } catch (err) { const raw = (err as Error).message; try { const parsed = JSON.parse(raw) as { detail?: Array<{ loc?: (string | number)[]; msg?: string }> }; const mapped: Record<string, string> = {}; for (const item of parsed.detail ?? []) { const field = String(item.loc?.[item.loc.length - 1] ?? "form"); mapped[field] = item.msg ?? "Invalid value"; } setErrors(mapped); } catch { setMessage(raw); } } }
  return <div className="grid gap-4"><SectionHeader title="Settings" description="Runtime configuration for fetching, engine behavior, and profile metadata." /><form onSubmit={onSave} className="grid gap-4">{Object.entries(SECTIONS).map(([section, fields]) => <Card key={section}><h3 className="text-base font-semibold">{section}</h3><div className="grid gap-3 md:grid-cols-2">{fields.map((k) => <label key={k} className="grid gap-2 text-sm text-text-subtle">{k}<Input value={form[k] ?? ""} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />{errors[k] ? <small className="text-danger">{errors[k]}</small> : null}</label>)}</div></Card>)}<div className="flex flex-wrap gap-2"><Button type="submit" variant="primary">Save settings</Button><Button type="button" onClick={() => runFetchGames()}>Fetch games</Button></div>{message ? <p className="text-sm text-text-subtle">{message}</p> : null}</form></div>;
}
