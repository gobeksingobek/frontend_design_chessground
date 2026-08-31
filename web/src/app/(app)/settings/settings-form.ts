export const INITIAL_FORM: Record<string, string> = {
  daysBack: "180",
  chesscomUsernames: "",
  lichessUsernames: "",
  variants: "",
  engineDepth: "20",
  maxPlies: "30",
  reviewTopN: "25",
  tabiyaTopN: "10",
  matchingMode: "STRICT",
  missingCoverageProposalThreshold: "5",
  enableEngineCache: "true",
  incrementalAnalysis: "true",
  playerName: "",
  playerNames: "",
  ratingBandSize: "100",
};

export const SECTIONS = [
  { title: "Analysis", fields: ["engineDepth", "maxPlies", "enableEngineCache", "incrementalAnalysis", "reviewTopN", "tabiyaTopN", "matchingMode", "missingCoverageProposalThreshold"] as const },
  { title: "Profile", fields: ["playerName", "playerNames", "ratingBandSize"] as const },
  { title: "Fetch", fields: ["chesscomUsernames", "lichessUsernames", "variants", "daysBack"] as const },
] as const;

export const LABELS: Record<string, string> = {
  daysBack: "Days back",
  chesscomUsernames: "Chess.com usernames",
  lichessUsernames: "Lichess usernames",
  variants: "Variants",
  engineDepth: "Engine depth",
  maxPlies: "Max plies",
  enableEngineCache: "Enable engine cache",
  incrementalAnalysis: "Incremental analysis",
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
  engine_depth: "engineDepth",
  max_plies: "maxPlies",
  enable_engine_cache: "enableEngineCache",
  incremental_analysis: "incrementalAnalysis",
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
