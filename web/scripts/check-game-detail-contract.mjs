function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function checkCanonicalGameDetail(payload) {
  assert(isObject(payload), "GET /games/{id} payload must be an object");
  assert(isObject(payload.header), "GET /games/{id}.header must be an object");
  assert(Array.isArray(payload.moves), "GET /games/{id}.moves must be an array");

  assert(isObject(payload.navigation), "GET /games/{id}.navigation must be an object");
  for (const field of ["current_game_id", "prev_game_id", "next_game_id"]) {
    assert(payload.navigation[field] === null || Number.isInteger(payload.navigation[field]), `GET /games/{id}.navigation.${field} must be int|null`);
  }
  assert(Array.isArray(payload.navigation.bookmarked_ply_ids), "GET /games/{id}.navigation.bookmarked_ply_ids must be an array");
  for (const ply of payload.navigation.bookmarked_ply_ids) {
    assert(Number.isInteger(ply), "GET /games/{id}.navigation.bookmarked_ply_ids entries must be integers");
  }
  for (const field of ["can_jump_start", "can_jump_end"]) {
    assert(typeof payload.navigation[field] === "boolean", `GET /games/{id}.navigation.${field} must be boolean`);
  }

  for (const field of ["prev_game_id", "next_game_id"]) {
    assert(payload[field] === null || Number.isInteger(payload[field]), `GET /games/{id}.${field} must be int|null`);
  }
  for (const field of ["prev_game_label", "next_game_label"]) {
    assert(payload[field] === null || typeof payload[field] === "string", `GET /games/{id}.${field} must be string|null`);
  }
}

checkCanonicalGameDetail({
  header: { id: 42, result: "1-0" },
  moves: [{ ply: 1, pos_id: 1 }],
  prev_game_id: 43,
  next_game_id: 41,
  prev_game_label: "Carlsen vs Nepomniachtchi (2024.01.01)",
  next_game_label: null,
  navigation: {
    current_game_id: 42,
    prev_game_id: 43,
    next_game_id: 41,
    bookmarked_ply_ids: [],
    can_jump_start: true,
    can_jump_end: true,
  },
});

console.log("Game detail contract checks passed for canonical GET /games/{id} navigation fields.");
