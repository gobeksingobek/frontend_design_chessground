from backend.read_api import _apply_games_filters, _normalize_compliance_min, _normalize_games_sort, _sort_games


def test_games_filter_combination_date_result_line_player_and_compliance() -> None:
    rows = [
        {
            "id": 1,
            "date": "2024.01.01",
            "result": "1-0",
            "line_id": "line-a",
            "compliance": "FULLY_COMPLIANT",
            "white": "Alpha",
            "black": "Beta",
        },
        {
            "id": 2,
            "date": "2024.01.03",
            "result": "1-0",
            "line_id": "line-a",
            "compliance": "PARTIALLY_COMPLIANT",
            "white": "Gamma",
            "black": "Alpha",
        },
        {
            "id": 3,
            "date": "2024.01.02",
            "result": "0-1",
            "line_id": "line-b",
            "compliance": "FULLY_COMPLIANT",
            "white": "Alpha",
            "black": "Delta",
        },
    ]

    filtered = _apply_games_filters(
        rows,
        result="1-0",
        line_id="line-a",
        player="alpha",
        date_from="2024.01.02",
        date_to="2024.01.03",
        compliance_min=0.5,
    )
    assert [row["id"] for row in filtered] == [2]


def test_games_filter_combination_result_and_date_window() -> None:
    rows = [
        {"id": 1, "date": "2024.01.01", "result": "1-0", "compliance": "FULLY_COMPLIANT", "line_id": "l1", "white": "A", "black": "B"},
        {"id": 2, "date": "2024.01.02", "result": "1/2-1/2", "compliance": "FULLY_COMPLIANT", "line_id": "l1", "white": "A", "black": "B"},
        {"id": 3, "date": "2024.01.03", "result": "1-0", "compliance": "FULLY_COMPLIANT", "line_id": "l2", "white": "A", "black": "B"},
    ]
    filtered = _apply_games_filters(rows, result="1-0", date_from="2024.01.02", date_to="2024.01.03")
    assert [row["id"] for row in filtered] == [3]


def test_games_default_ordering_date_desc_with_id_tiebreaker() -> None:
    rows = [
        {"id": 1, "date": "2024.01.02", "result": "1-0", "compliance": "FULLY_COMPLIANT"},
        {"id": 3, "date": "2024.01.02", "result": "1-0", "compliance": "FULLY_COMPLIANT"},
        {"id": 2, "date": "2024.01.01", "result": "0-1", "compliance": "NON_COMPLIANT"},
    ]
    ordered = _sort_games(rows, "date", "desc")
    assert [row["id"] for row in ordered] == [3, 1, 2]


def test_games_default_ordering_when_sort_args_invalid() -> None:
    rows = [
        {"id": 2, "date": "2024.01.01", "result": "1-0", "compliance": "FULLY_COMPLIANT"},
        {"id": 1, "date": "2024.01.02", "result": "0-1", "compliance": "NON_COMPLIANT"},
    ]
    sort_by, sort_dir = _normalize_games_sort("bad", "bad")
    assert (sort_by, sort_dir) == ("date", "desc")
    ordered = _sort_games(rows, sort_by, sort_dir)
    assert [row["id"] for row in ordered] == [1, 2]


def test_games_sort_and_compliance_min_normalization() -> None:
    assert _normalize_games_sort(None, None) == ("date", "desc")
    assert _normalize_games_sort("unknown", "sideways") == ("date", "desc")
    assert _normalize_games_sort("RESULT", "ASC") == ("result", "asc")

    assert _normalize_compliance_min(None) is None
    assert _normalize_compliance_min(-1.0) == 0.0
    assert _normalize_compliance_min(0.25) == 0.25
    assert _normalize_compliance_min(2.0) == 1.0
