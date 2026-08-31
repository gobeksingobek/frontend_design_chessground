from __future__ import annotations

from backend.read_api import build_position_intelligence_payload


def test_position_intelligence_uses_persisted_summary_and_tree_rows() -> None:
    payload = build_position_intelligence_payload(
        pos_id=1,
        my_side_only=True,
        repertoire_rows=[{"uci_move": "e2e4", "san_move": "e4", "next_pos_id": 2, "weight": 2}],
        game_rows=[{"uci_move": "e2e4", "games": 2, "wins": 1, "draws": 1, "losses": 0}],
        summary={"position": {"pos_id": 1, "fen": "fen", "side_to_move": "w"}, "totals": {"games": 2, "wins": 1, "draws": 1}},
    )
    assert payload["coverage"]["coverage_pct"] == 100.0
    assert payload["outcome_summary"]["games"] == 2
    assert payload["position"]["fen"] == "fen"
