from backend.read_api import _normalize_insight_row, _sort_insights


def test_insight_row_adds_priority_confidence_and_refs() -> None:
    row = _normalize_insight_row(
        {
            "title": "t",
            "data": {
                "priority_score": 0.9,
                "confidence": 0.8,
                "source_refs": [{"type": "game", "id": "1", "label": "g1"}],
            },
        }
    )
    assert row["priority_score"] == 0.9
    assert row["confidence"] == 0.8
    assert row["source_refs"] == [{"type": "game", "id": "1", "label": "g1"}]


def test_insights_sort_by_priority_then_confidence_with_stable_title_tiebreak() -> None:
    rows = _sort_insights(
        [
            {"title": "medium-confidence", "priority_score": 0.9, "confidence": 0.4},
            {"title": "high-confidence", "priority_score": 0.9, "confidence": 0.8},
            {"title": "alpha", "priority_score": 0.9, "confidence": 0.4},
            {"title": "lower-priority", "priority_score": 0.7, "confidence": 1.0},
        ]
    )
    assert [row["title"] for row in rows] == ["high-confidence", "medium-confidence", "alpha", "lower-priority"]


def test_insight_row_defaults_source_refs_to_empty_list() -> None:
    row = _normalize_insight_row({"title": "missing refs", "data": {"priority_score": 0.4, "confidence": 0.2}})
    assert row["source_refs"] == []


def test_insight_row_enforces_structured_source_refs() -> None:
    row = _normalize_insight_row(
        {
            "title": "cleanup",
            "data": {
                "source_refs": [
                    {"type": "line", "id": "l-1", "label": "Line one"},
                    {"type": "game", "id": "g-2"},
                    {"type": "", "id": "bad"},
                    {"type": "game"},
                    "bad-type",
                ]
            },
        }
    )
    assert row["source_refs"] == [
        {"type": "line", "id": "l-1", "label": "Line one"},
        {"type": "game", "id": "g-2", "label": "game:g-2"},
    ]
