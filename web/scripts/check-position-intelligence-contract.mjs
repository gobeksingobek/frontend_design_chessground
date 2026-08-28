function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const payload = {
  pos_id: 1,
  my_side_only: true,
  position: { pos_id: 1, fen: "startpos w", side_to_move: "w" },
  repertoire_continuations: [{ uci_move: "e2e4", san_move: "e4", next_pos_id: 2, weight: 3, is_priority_edge: 1, is_user_mainline: 1, is_sideline_pending: 0 }],
  game_continuations: [{ uci_move: "e2e4", san_move: "e4", next_pos_id: 2, games: 2, wins: 1, draws: 0, losses: 1, avg_opp_elo: 1600, score_pct: 50 }],
  coverage: {
    total_repertoire_moves: 1,
    covered_by_games: 1,
    coverage_pct: 100,
    total_games: 2,
    opponent_deviation_count: 0,
    played_repertoire_moves: 1,
    played_non_repertoire_moves: 0,
  },
  outcome_summary: { games: 2, wins: 1, draws: 0, losses: 1, score_pct: 50 },
  evaluation_summary: { avg_exit_eval_cp: 22, avg_your_cpl: 30, avg_rep_cpl: 12, latest_eval_cp: 18, best_uci: "e2e4", depth: 16, engine_id: "stockfish" },
  recent_games: [{ game_id: 10, date: "2024.01.01", white: "Me", black: "Opponent", result: "1-0", player_color: "white", ply: 1, san_move: "e4", uci_move: "e2e4", repertoire_class: "in_main", post_eval_cp: 22, your_cpl: 10 }],
  evidence: { repertoire_move_count: 1, game_move_count: 1, recent_game_count: 1, matters: ["2 recent-game samples reach this position"] },
};

assert(Number.isInteger(payload.pos_id), "pos_id must be an integer");
assert(payload.position.pos_id === payload.pos_id, "position.pos_id must match root pos_id");
assert(Array.isArray(payload.repertoire_continuations), "repertoire_continuations must be an array");
assert(Array.isArray(payload.game_continuations), "game_continuations must be an array");
assert(typeof payload.coverage.coverage_pct === "number", "coverage_pct must be numeric");
assert(typeof payload.coverage.opponent_deviation_count === "number", "opponent deviation count must be numeric");
assert(typeof payload.outcome_summary.score_pct === "number", "outcome score_pct must be numeric");
assert("avg_exit_eval_cp" in payload.evaluation_summary, "evaluation summary must include avg_exit_eval_cp");
assert(Array.isArray(payload.recent_games), "recent_games must be an array");
assert(Array.isArray(payload.evidence.matters), "evidence.matters must be an array");

console.log("position intelligence contract ok");
