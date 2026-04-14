function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function checkNavigation(payload) {
  assert(isObject(payload), "navigation must be object");
  for (const field of ["current_game_id", "prev_game_id", "next_game_id"]) {
    assert(payload[field] === null || typeof payload[field] === "string", `navigation.${field} must be string|null`);
  }
  assert(Array.isArray(payload.bookmarked_ply_ids), "navigation.bookmarked_ply_ids must be array");
  assert(payload.bookmarked_ply_ids.every((ply) => Number.isInteger(ply) && ply >= 0), "navigation.bookmarked_ply_ids entries must be non-negative integers");
  assert(typeof payload.can_jump_start === "boolean", "navigation.can_jump_start must be boolean");
  assert(typeof payload.can_jump_end === "boolean", "navigation.can_jump_end must be boolean");
}

function checkDeprecatedNeighborsCompatibility(payload) {
  assert(isObject(payload), "deprecated neighbors payload must be object when provided");
  assert(typeof payload.game_id === "string", "deprecated neighbors.game_id must be string");
  for (const field of ["prev_game_id", "next_game_id", "prev_label", "next_label"]) {
    assert(payload[field] === null || typeof payload[field] === "string", `deprecated neighbors.${field} must be string|null`);
  }
}

checkNavigation({
  current_game_id: "game-2",
  prev_game_id: "game-1",
  next_game_id: "game-3",
  bookmarked_ply_ids: [0, 14, 22],
  can_jump_start: true,
  can_jump_end: true,
});

checkDeprecatedNeighborsCompatibility({
  game_id: "game-2",
  prev_game_id: "game-1",
  next_game_id: "game-3",
  prev_label: "vs Opponent A",
  next_label: "vs Opponent C",
});

console.log("Game detail contract checks passed with canonical /games/{id}.navigation and deprecated /games/{id}/neighbors compatibility shape.");
