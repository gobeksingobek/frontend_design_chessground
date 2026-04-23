function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const browse = {
  pos_id: 1,
  my_side_only: true,
  repertoire_children: [{ uci_move: "e2e4" }],
  game_children: [{ uci_move: "e2e4" }],
};
const coverage = {
  pos_id: 1,
  my_side_only: true,
  repertoire_children: [{ uci_move: "e2e4" }],
  game_children: [{ uci_move: "e2e4" }],
  total_repertoire_moves: 1,
  covered_by_games: 1,
  coverage_pct: 100,
};
const metrics = {
  pos_id: 1,
  my_side_only: true,
  repertoire_children: [{ uci_move: "e2e4" }],
  game_children: [{ uci_move: "e2e4" }],
  top_repertoire_branches: [{ uci_move: "e2e4" }],
  top_game_branches: [{ uci_move: "e2e4" }],
};

assert(browse.pos_id === coverage.pos_id && coverage.pos_id === metrics.pos_id, "pos_id mismatch across tree endpoints");
assert(browse.my_side_only === coverage.my_side_only && coverage.my_side_only === metrics.my_side_only, "my_side_only mismatch across tree endpoints");
assert(Array.isArray(coverage.repertoire_children) && Array.isArray(metrics.repertoire_children), "missing mirrored repertoire_children");
assert(Array.isArray(coverage.game_children) && Array.isArray(metrics.game_children), "missing mirrored game_children");
assert(coverage.total_repertoire_moves === coverage.repertoire_children.length, "coverage total does not match mirrored repertoire children");

console.log("Tree contract verified across browse, coverage, and branch-metrics schemas.");
