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
});

console.log("Game detail contract checks passed for canonical GET /games/{id} neighbor fields.");
