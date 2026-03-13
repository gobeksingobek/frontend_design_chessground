"use client";

import { FormEvent, useEffect, useState } from "react";

import { getRuntimeSettings, runFetchGames, updateRuntimeSettings } from "@/lib/api-client";

function toList(value: string): string[] { return value.split(",").map((v) => v.trim()).filter(Boolean); }

export default function SettingsPage() {
  const [form, setForm] = useState<Record<string, string>>({ daysBack: "180", chesscomUsernames: "", lichessUsernames: "", variants: "", gamesDir: "", databasePath: "", repertoireDir: "", stockfishPath: "", pieceDir: "", engineDepth: "20", engineThreads: "1", engineHashMb: "0", engineMaxTimeMs: "300", playerName: "", playerNames: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");

  useEffect(() => { getRuntimeSettings().then((s) => setForm((f) => ({ ...f, daysBack: String(s.days_back), chesscomUsernames: s.chesscom_usernames.join(", "), lichessUsernames: s.lichess_usernames.join(", "), variants: s.variants.join(", "), gamesDir: s.games_dir ?? "", databasePath: s.database_path ?? "", repertoireDir: s.repertoire_dir ?? "", stockfishPath: s.stockfish_path ?? "", pieceDir: s.piece_dir ?? "", engineDepth: String(s.engine_depth ?? 20), engineThreads: String(s.engine_threads ?? 1), engineHashMb: String(s.engine_hash_mb ?? 0), engineMaxTimeMs: String(s.engine_max_time_ms ?? 300), playerName: s.player_name ?? "", playerNames: s.player_names.join(", ") }))); }, []);

  async function onSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({});
    try {
      await updateRuntimeSettings({
        days_back: Number(form.daysBack), chesscom_usernames: toList(form.chesscomUsernames), lichess_usernames: toList(form.lichessUsernames), variants: toList(form.variants), games_dir: form.gamesDir, database_path: form.databasePath, repertoire_dir: form.repertoireDir, stockfish_path: form.stockfishPath, piece_dir: form.pieceDir, engine_depth: Number(form.engineDepth), engine_threads: Number(form.engineThreads), engine_hash_mb: Number(form.engineHashMb), engine_max_time_ms: Number(form.engineMaxTimeMs), player_name: form.playerName, player_names: toList(form.playerNames),
      });
      setMessage("Settings saved.");
    } catch (err) {
      const raw = (err as Error).message;
      try {
        const parsed = JSON.parse(raw) as { detail?: Array<{ loc?: (string|number)[]; msg?: string }> };
        const mapped: Record<string, string> = {};
        for (const item of parsed.detail ?? []) {
          const field = String(item.loc?.[item.loc.length - 1] ?? "form");
          mapped[field] = item.msg ?? "Invalid value";
        }
        setErrors(mapped);
      } catch { setMessage(raw); }
    }
  }

  return <div className="stack"><h2>Settings</h2><form className="card stack" onSubmit={onSave}>
    <h3>Fetch</h3>{["chesscomUsernames","lichessUsernames","variants","daysBack"].map((k)=><label key={k}>{k}<input value={form[k] ?? ""} onChange={(e)=>setForm({...form,[k]:e.target.value})} />{errors[k] ? <small className="warn">{errors[k]}</small> : null}</label>)}
    <h3>Paths</h3>{["gamesDir","databasePath","repertoireDir","stockfishPath","pieceDir"].map((k)=><label key={k}>{k}<input value={form[k] ?? ""} onChange={(e)=>setForm({...form,[k]:e.target.value})} />{errors[k] ? <small className="warn">{errors[k]}</small> : null}</label>)}
    <h3>Engine</h3>{["engineDepth","engineThreads","engineHashMb","engineMaxTimeMs"].map((k)=><label key={k}>{k}<input value={form[k] ?? ""} onChange={(e)=>setForm({...form,[k]:e.target.value})} />{errors[k] ? <small className="warn">{errors[k]}</small> : null}</label>)}
    <h3>Profile</h3>{["playerName","playerNames"].map((k)=><label key={k}>{k}<input value={form[k] ?? ""} onChange={(e)=>setForm({...form,[k]:e.target.value})} />{errors[k] ? <small className="warn">{errors[k]}</small> : null}</label>)}
    <button type="submit">Save settings</button><button type="button" onClick={()=>runFetchGames()}>Fetch games</button>{message ? <p>{message}</p> : null}
  </form></div>;
}
