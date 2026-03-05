"use client";

import { FormEvent, useEffect, useState } from "react";

import { getRuntimeSettings, runFetchGames, updateRuntimeSettings } from "@/lib/api-client";

function toList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function SettingsPage() {
  const [chesscomUsernames, setChesscomUsernames] = useState("");
  const [lichessUsernames, setLichessUsernames] = useState("");
  const [variants, setVariants] = useState("");
  const [daysBack, setDaysBack] = useState("180");

  const [loadState, setLoadState] = useState<"idle" | "loading" | "error">("idle");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [fetchState, setFetchState] = useState<"idle" | "running" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let mounted = true;
    setLoadState("loading");
    getRuntimeSettings()
      .then((settings) => {
        if (!mounted) return;
        setChesscomUsernames(settings.chesscom_usernames.join(", "));
        setLichessUsernames(settings.lichess_usernames.join(", "));
        setVariants(settings.variants.join(", "));
        setDaysBack(String(settings.days_back));
        setLoadState("idle");
      })
      .catch((err) => {
        if (!mounted) return;
        setLoadState("error");
        setMessage((err as Error).message);
      });

    return () => {
      mounted = false;
    };
  }, []);

  async function onSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaveState("saving");
    setMessage("");

    const parsedDaysBack = Number(daysBack);
    if (!Number.isInteger(parsedDaysBack) || parsedDaysBack < 1) {
      setSaveState("error");
      setMessage("Days back must be a positive integer.");
      return;
    }

    try {
      const updated = await updateRuntimeSettings({
        chesscom_usernames: toList(chesscomUsernames),
        lichess_usernames: toList(lichessUsernames),
        variants: toList(variants),
        days_back: parsedDaysBack,
      });
      setChesscomUsernames(updated.chesscom_usernames.join(", "));
      setLichessUsernames(updated.lichess_usernames.join(", "));
      setVariants(updated.variants.join(", "));
      setDaysBack(String(updated.days_back));
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
        <label className="stack">
          <span>Chess.com usernames (comma-separated)</span>
          <input value={chesscomUsernames} onChange={(event) => setChesscomUsernames(event.target.value)} />
        </label>

        <label className="stack">
          <span>Lichess usernames (comma-separated)</span>
          <input value={lichessUsernames} onChange={(event) => setLichessUsernames(event.target.value)} />
        </label>

        <label className="stack">
          <span>Variants (comma-separated)</span>
          <input value={variants} onChange={(event) => setVariants(event.target.value)} />
        </label>

        <label className="stack">
          <span>Days back</span>
          <input type="number" min={1} value={daysBack} onChange={(event) => setDaysBack(event.target.value)} />
        </label>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button type="submit" disabled={saveState === "saving" || loadState === "loading"}>Save settings</button>
          <button type="button" disabled={fetchState === "running"} onClick={onFetchGames}>Fetch games</button>
        </div>

        {message ? <p className={saveState === "error" || fetchState === "error" ? "warn" : "ok"}>{message}</p> : null}
      </form>
    </div>
  );
}
