export const INITIAL_FORM: Record<string, string> = {
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

export const LABELS: Record<string, string> = {
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

export function toList(value: string): string[] {
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
