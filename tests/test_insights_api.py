from backend.read_api import _normalize_insight_row, _sort_insights


def test_insight_row_adds_priority_confidence_and_refs() -> None:
    row = _normalize_insight_row({"title": "t", "data": {"priority_score": 0.9, "confidence": 0.8, "source_refs": [{"type": "game", "id": "1", "label": "g1"}]}})
    assert row["priority_score"] == 0.9
    assert row["confidence"] == 0.8
    assert len(row["source_refs"]) == 1


def test_insights_sort_by_priority_then_confidence() -> None:
    rows = _sort_insights(
        [
            {"title": "medium-confidence", "priority_score": 0.9, "confidence": 0.4},
            {"title": "high-confidence", "priority_score": 0.9, "confidence": 0.8},
            {"title": "lower-priority", "priority_score": 0.7, "confidence": 1.0},
        ]
    )
    assert [row["title"] for row in rows] == ["high-confidence", "medium-confidence", "lower-priority"]


def test_insight_row_defaults_source_refs_to_empty_list() -> None:
    row = _normalize_insight_row({"title": "missing refs", "data": {"priority_score": 0.4, "confidence": 0.2}})
    assert row["source_refs"] == []
