from backend.api_service import TreeBrowseResponse, TreeCoverageResponse


def test_tree_contract_core_fields() -> None:
    browse = TreeBrowseResponse(pos_id=1, my_side_only=True, repertoire_children=[], game_children=[])
    coverage = TreeCoverageResponse(pos_id=1, total_repertoire_moves=0, covered_by_games=0, coverage_pct=0.0)
    assert browse.pos_id == coverage.pos_id
