import test from "node:test";
import assert from "node:assert/strict";

import {
  toCanonicalTreeContract,
  toCanonicalTreeSnapshot,
  toNavigablePositionId,
  toPositionIntelligencePanelState,
  toPositionIntelligenceSnapshot,
} from "@/components/tree/tree-explorer-shared";

test("tree branch navigation accepts only persisted position ids", () => {
  assert.equal(toNavigablePositionId(42), 42);
  assert.equal(toNavigablePositionId(null), null);
  assert.equal(toNavigablePositionId(0), null);
  assert.equal(toNavigablePositionId(-1), null);
});

test("tree canonical schema snapshot values", () => {
  const snapshot = toCanonicalTreeSnapshot(
    { pos_id: 2, my_side_only: true, repertoire_children: [{}], game_children: [{}, {}] },
    { pos_id: 2, my_side_only: true, coverage_pct: 50, total_repertoire_moves: 1, covered_by_games: 1, repertoire_children: [{}], game_children: [{}, {}] },
    { pos_id: 2, my_side_only: true, repertoire_children: [{}], game_children: [{}, {}], top_repertoire_branches: [{}], top_game_branches: [{}] },
  );

  assert.equal(snapshot.posId, 2);
  assert.equal(snapshot.coveragePct, 50);
  assert.equal(snapshot.repertoireCount, 1);
  assert.equal(snapshot.gameCount, 2);
});

test("tree canonical schema keeps node identity and coverage across panels", () => {
  const canonical = toCanonicalTreeContract({
    browse: { pos_id: 7, my_side_only: true, repertoire_children: [{ uci_move: "g1f3" } as never, { uci_move: "c2c4" } as never], game_children: [{ uci_move: "g1f3" } as never] },
    coverage: { pos_id: 7, my_side_only: true, repertoire_children: [] as never[], game_children: [] as never[], total_repertoire_moves: 2, covered_by_games: 1, coverage_pct: 50 },
  });
  const snapshot = toCanonicalTreeSnapshot(canonical.browse, canonical.coverage, canonical.metrics);

  assert.equal(canonical.browse.pos_id, canonical.coverage.pos_id);
  assert.equal(canonical.coverage.pos_id, canonical.metrics.pos_id);
  assert.equal(snapshot.posId, 7);
  assert.equal(snapshot.coveragePct, 50);
  assert.equal(snapshot.repertoireCount, 2);
  assert.equal(snapshot.gameCount, 1);
});

test("tree canonical schema falls back to mirrored coverage counts", () => {
  const snapshot = toCanonicalTreeSnapshot(
    null,
    { pos_id: 9, my_side_only: true, coverage_pct: 62.5, repertoire_children: [{}, {}, {}] as never[], game_children: [{}, {}] as never[], total_repertoire_moves: 3, covered_by_games: 2 },
    null,
  );

  assert.equal(snapshot.posId, 9);
  assert.equal(snapshot.coveragePct, 62.5);
  assert.equal(snapshot.repertoireCount, 3);
  assert.equal(snapshot.gameCount, 2);
});

test("position intelligence snapshot exposes loaded summary state", () => {
  const snapshot = toPositionIntelligenceSnapshot({
    pos_id: 12,
    my_side_only: true,
    position: { pos_id: 12, fen: "fen", side_to_move: "w" },
    repertoire_continuations: [{ uci_move: "e2e4", san_move: "e4", next_pos_id: 13, weight: 2, is_priority_edge: 1, is_user_mainline: 1, is_sideline_pending: 0 }],
    game_continuations: [{ uci_move: "e2e4", san_move: "e4", next_pos_id: 13, games: 3, wins: 2, draws: 0, losses: 1, avg_opp_elo: 1500, score_pct: 66.7 }],
    coverage: { total_repertoire_moves: 1, covered_by_games: 1, coverage_pct: 100, total_games: 3, opponent_deviation_count: 0, played_repertoire_moves: 1, played_non_repertoire_moves: 0 },
    outcome_summary: { games: 3, wins: 2, draws: 0, losses: 1, score_pct: 66.7 },
    evaluation_summary: { avg_exit_eval_cp: 10, avg_your_cpl: 20, avg_rep_cpl: 5, latest_eval_cp: 12, best_uci: "e2e4", depth: 16, engine_id: "stockfish" },
    recent_games: [{ game_id: 1, date: "2024.01.01", white: "Me", black: "Opp", result: "1-0", player_color: "white", ply: 1, san_move: "e4", uci_move: "e2e4", repertoire_class: "in_main", post_eval_cp: 10, your_cpl: 20 }],
    evidence: { repertoire_move_count: 1, game_move_count: 1, recent_game_count: 1, matters: ["3 samples"] },
  });

  assert.equal(snapshot.posId, 12);
  assert.equal(snapshot.coveragePct, 100);
  assert.equal(snapshot.repertoireMoveCount, 1);
  assert.equal(snapshot.gameMoveCount, 1);
  assert.equal(snapshot.recentGameCount, 1);
  assert.equal(snapshot.hasEvidence, true);
});

test("position intelligence snapshot handles empty state", () => {
  const snapshot = toPositionIntelligenceSnapshot(null);

  assert.equal(snapshot.coveragePct, 0);
  assert.equal(snapshot.repertoireMoveCount, 0);
  assert.equal(snapshot.gameMoveCount, 0);
  assert.equal(snapshot.recentGameCount, 0);
  assert.equal(snapshot.hasEvidence, false);
});

test("position intelligence panel renders loaded summary state", () => {
  const panel = toPositionIntelligencePanelState({
    pos_id: 12,
    my_side_only: true,
    position: { pos_id: 12, fen: "fen", side_to_move: "w" },
    repertoire_continuations: [{ uci_move: "e2e4", san_move: "e4", next_pos_id: 13, weight: 2, is_priority_edge: 1, is_user_mainline: 1, is_sideline_pending: 0 }],
    game_continuations: [{ uci_move: "c2c4", san_move: "c4", next_pos_id: 14, games: 4, wins: 1, draws: 1, losses: 2, avg_opp_elo: 1500, score_pct: 37.5 }],
    coverage: { total_repertoire_moves: 1, covered_by_games: 0, coverage_pct: 0, total_games: 4, opponent_deviation_count: 2, played_repertoire_moves: 0, played_non_repertoire_moves: 1 },
    outcome_summary: { games: 4, wins: 1, draws: 1, losses: 2, score_pct: 37.5 },
    evaluation_summary: { avg_exit_eval_cp: -30, avg_your_cpl: 80, avg_rep_cpl: 12, latest_eval_cp: null, best_uci: null, depth: null, engine_id: null },
    recent_games: [{ game_id: 22, date: "2024.03.01", white: "Me", black: "Opp", result: "0-1", player_color: "white", ply: 5, san_move: "c4", uci_move: "c2c4", repertoire_class: "out_rep", post_eval_cp: -30, your_cpl: 80 }],
    evidence: { repertoire_move_count: 1, game_move_count: 1, recent_game_count: 1, matters: ["4 recent-game samples reach this position"] },
  });

  assert.equal(panel.status, "ready");
  assert.deepEqual(panel.topRepertoireMoves, ["e4 (2)"]);
  assert.deepEqual(panel.topGameMoves, ["c4 (4)"]);
  assert.deepEqual(panel.matters, ["4 recent-game samples reach this position"]);
  assert.deepEqual(panel.recentGameLabels, ["Game #22 ply 5: c4 - 0-1"]);
});

test("position intelligence panel handles loading and empty states", () => {
  assert.equal(toPositionIntelligencePanelState(null).status, "loading");

  const empty = toPositionIntelligencePanelState({
    pos_id: 99,
    my_side_only: true,
    position: { pos_id: 99, fen: "empty w", side_to_move: "w" },
    repertoire_continuations: [],
    game_continuations: [],
    coverage: { total_repertoire_moves: 0, covered_by_games: 0, coverage_pct: 0, total_games: 0, opponent_deviation_count: 0, played_repertoire_moves: 0, played_non_repertoire_moves: 0 },
    outcome_summary: { games: 0, wins: 0, draws: 0, losses: 0, score_pct: 0 },
    evaluation_summary: { avg_exit_eval_cp: null, avg_your_cpl: null, avg_rep_cpl: null, latest_eval_cp: null, best_uci: null, depth: null, engine_id: null },
    recent_games: [],
    evidence: { repertoire_move_count: 0, game_move_count: 0, recent_game_count: 0, matters: [] },
  });

  assert.equal(empty.status, "empty");
  assert.deepEqual(empty.topRepertoireMoves, []);
  assert.deepEqual(empty.topGameMoves, []);
  assert.deepEqual(empty.recentGameLabels, []);
});
