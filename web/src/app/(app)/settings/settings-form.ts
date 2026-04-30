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
  engineWorkers: "0",
  engineWorkerCap: "4",
  engineMode: "adaptive",
  engineProfile: "aggressive",
  reviewTopN: "25",
  tabiyaTopN: "10",
  matchingMode: "STRICT",
  missingCoverageProposalThreshold: "5",
  enableEngineCache: "true",
  incrementalAnalysis: "true",
  engineCachePruneNonActive: "true",
  playerName: "",
  playerNames: "",
  ratingBandSize: "100",
};

export const SECTIONS = [
  { title: "Paths", fields: ["gamesDir", "databasePath", "repertoireDir", "stockfishPath", "pieceDir"] as const },
  { title: "Engine", fields: ["engineDepth", "maxPlies", "engineThreads", "engineHashMb", "engineMaxTimeMs", "engineWorkers", "engineWorkerCap", "engineMode", "engineProfile", "enableEngineCache", "incrementalAnalysis", "engineCachePruneNonActive", "reviewTopN", "tabiyaTopN", "matchingMode", "missingCoverageProposalThreshold"] as const },
  { title: "Profile", fields: ["playerName", "playerNames", "ratingBandSize"] as const },
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
  engineWorkers: "Engine workers",
  engineWorkerCap: "Engine worker cap",
  engineMode: "Engine mode",
  engineProfile: "Engine profile",
  enableEngineCache: "Enable engine cache",
  incrementalAnalysis: "Incremental analysis",
  engineCachePruneNonActive: "Prune non-active cache",
  reviewTopN: "Review top N",
  tabiyaTopN: "Tabiya top N",
  matchingMode: "Matching mode",
  missingCoverageProposalThreshold: "Missing coverage threshold",
  playerName: "Player name",
  playerNames: "Player aliases",
  ratingBandSize: "Rating band size",
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
  engine_workers: "engineWorkers",
  engine_worker_cap: "engineWorkerCap",
  engine_mode: "engineMode",
  engine_profile: "engineProfile",
  enable_engine_cache: "enableEngineCache",
  incremental_analysis: "incrementalAnalysis",
  engine_cache_prune_non_active: "engineCachePruneNonActive",
  review_top_n: "reviewTopN",
  tabiya_top_n: "tabiyaTopN",
  matching_mode: "matchingMode",
  missing_coverage_proposal_threshold: "missingCoverageProposalThreshold",
  player_name: "playerName",
  player_names: "playerNames",
  rating_band_size: "ratingBandSize",
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
      if (item.code === "type") mapped[key] = "Invalid value type";
      else if (item.code === "range") mapped[key] = item.message || "Value out of range";
      else if (item.code === "min_items") mapped[key] = "Enter at least one item";
      else mapped[key] = item.message || item.code || "Invalid value";
    }
    return mapped;
  } catch {
    return {};
  }
}
