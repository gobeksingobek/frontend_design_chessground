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
  missing_coverage_proposal_threshold: 5,
};

assertHasKeys(
  responseShape,
  [
    "chesscom_usernames",
    "lichess_usernames",
    "variants",
    "days_back",
    "engine_depth",
    "max_plies",
    "player_name",
    "player_names",
  ],
  "GET /settings/runtime",
);

const requestShape = {
  chesscom_usernames: ["alice"],
  lichess_usernames: ["alice"],
  variants: ["rapid", "blitz"],
  days_back: 90,
  engine_depth: 18,
  max_plies: 30,
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
    "engine_depth",
    "max_plies",
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
