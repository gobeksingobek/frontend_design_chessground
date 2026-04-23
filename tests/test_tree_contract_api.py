from backend.api_service import TreeBranchMetricsResponse, TreeBrowseResponse, TreeCoverageResponse
from backend.read_api import build_tree_contract_payload


def test_tree_contract_cross_endpoint_schema_consistency() -> None:
    payload = build_tree_contract_payload(
        pos_id=12,
        my_side_only=True,
        repertoire_rows=[{"uci_move": "e2e4", "san_move": "e4", "next_pos_id": 15, "weight": 3}],
        game_rows=[{"uci_move": "e2e4", "san_move": "e4", "next_pos_id": 15, "games": 2, "wins": 1, "draws": 1, "losses": 0}],
    )
    browse = TreeBrowseResponse(**payload)
    coverage = TreeCoverageResponse(**payload)
    metrics = TreeBranchMetricsResponse(**payload)

    assert browse.pos_id == coverage.pos_id
    assert coverage.pos_id == metrics.pos_id
    assert coverage.my_side_only is True
    assert coverage.coverage_pct == 100.0
    assert coverage.total_repertoire_moves == len(coverage.repertoire_children)
    assert metrics.repertoire_children == coverage.repertoire_children
    assert metrics.game_children == coverage.game_children
    assert metrics.top_repertoire_branches[0]["uci_move"] == browse.repertoire_children[0].uci_move
