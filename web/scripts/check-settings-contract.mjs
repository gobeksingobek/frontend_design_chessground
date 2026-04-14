function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function assertHasKeys(obj, keys, context) {
  for (const key of keys) {
    assert(Object.prototype.hasOwnProperty.call(obj, key), `${context}: missing key '${key}'`);
  }
}

const responseShape = {
  chesscom_usernames: ["alice"],
  lichess_usernames: ["alice"],
  variants: ["rapid"],
  days_back: 180,
  games_dir: "/games",
  database_path: "/db.sqlite",
  repertoire_dir: "/rep",
  stockfish_path: "/stockfish",
  piece_dir: "/pieces",
  engine_depth: 20,
  max_plies: 30,
  player_name: "alice",
  player_names: ["alice", "ali"],
  rating_band_size: 100,
  matching_mode: "STRICT",
  enable_engine_cache: true,
  incremental_analysis: true,
  review_top_n: 25,
  tabiya_top_n: 10,
  engine_workers: 0,
  engine_worker_cap: 4,
  engine_threads: 1,
  engine_hash_mb: 0,
  engine_mode: "adaptive",
  engine_max_time_ms: 300,
  engine_profile: "aggressive",
  engine_cache_prune_non_active: true,
  missing_coverage_proposal_threshold: 5,
};

assertHasKeys(
  responseShape,
  [
    "chesscom_usernames",
    "lichess_usernames",
    "variants",
    "days_back",
    "games_dir",
    "database_path",
    "repertoire_dir",
    "stockfish_path",
    "piece_dir",
    "engine_depth",
    "max_plies",
    "player_name",
    "player_names",
    "engine_threads",
    "engine_hash_mb",
    "engine_max_time_ms",
  ],
  "GET /settings/runtime",
);

const requestShape = {
  chesscom_usernames: ["alice"],
  lichess_usernames: ["alice"],
  variants: ["rapid", "blitz"],
  days_back: 90,
  games_dir: "/games",
  database_path: "/db.sqlite",
  repertoire_dir: "/rep",
  stockfish_path: "/stockfish",
  piece_dir: "/pieces",
  engine_depth: 18,
  max_plies: 30,
  engine_threads: 2,
  engine_hash_mb: 64,
  engine_max_time_ms: 500,
  player_name: "alice",
  player_names: ["alice", "ali"],
};

assertHasKeys(
  requestShape,
  [
    "chesscom_usernames",
    "lichess_usernames",
    "variants",
    "days_back",
    "games_dir",
    "database_path",
    "repertoire_dir",
    "stockfish_path",
    "piece_dir",
    "engine_depth",
    "max_plies",
    "engine_threads",
    "engine_hash_mb",
    "engine_max_time_ms",
    "player_name",
    "player_names",
  ],
  "PUT /settings/runtime request",
);

const validationErrorShape = {
  detail: [{ field: "days_back", code: "range", message: "Must be between 1 and 3650" }],
};

assert(Array.isArray(validationErrorShape.detail), "PUT /settings/runtime 422 requires detail[]");
assertHasKeys(validationErrorShape.detail[0], ["field", "code", "message"], "PUT /settings/runtime 422 detail item");

console.log("Settings contract verified for GET/PUT /settings/runtime and validation error detail[] shape.");
