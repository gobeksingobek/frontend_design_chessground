from backend.read_api import _apply_games_filters


def test_games_filter_compliance_min_and_player() -> None:
    rows = [
        {"id": 1, "compliance": "FULLY_COMPLIANT", "white": "Alpha", "black": "B", "date": "2024.01.01"},
        {"id": 2, "compliance": "NON_COMPLIANT", "white": "C", "black": "D", "date": "2024.01.02"},
    ]
    filtered = _apply_games_filters(rows, compliance_min=0.5, player="alpha")
    assert [row["id"] for row in filtered] == [1]
