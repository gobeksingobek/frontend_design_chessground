from backend.read_api import _normalize_insight_row


def test_insight_row_adds_priority_confidence_and_refs() -> None:
    row = _normalize_insight_row({"title": "t", "data": {"priority_score": 0.9, "confidence": 0.8, "source_refs": [{"type": "game", "id": "1", "label": "g1"}]}})
    assert row["priority_score"] == 0.9
    assert row["confidence"] == 0.8
    assert len(row["source_refs"]) == 1
