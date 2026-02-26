from __future__ import annotations


def compute_time_usage_by_game(time_rows: list[dict]) -> dict[int, dict]:
    summary: dict[int, dict] = {}
    for row in time_rows:
        if row.get("is_daily"):
            continue
        if not row.get("is_self"):
            continue
        time_spent = row.get("time_spent_seconds")
        if time_spent is None:
            continue

        game_id = row["game_id"]
        rep_class = row.get("repertoire_class") or ""
        in_book = rep_class in {"IN_REPERTOIRE_MAIN", "IN_REPERTOIRE_OTHER"}
        entry = summary.setdefault(
            game_id,
            {
                "in_book_total": 0.0,
                "in_book_count": 0,
                "out_book_total": 0.0,
                "out_book_count": 0,
                "in_book_frac_total": 0.0,
                "in_book_frac_count": 0,
                "out_book_frac_total": 0.0,
                "out_book_frac_count": 0,
            },
        )

        if in_book:
            entry["in_book_total"] += time_spent
            entry["in_book_count"] += 1
        else:
            entry["out_book_total"] += time_spent
            entry["out_book_count"] += 1

        fraction = row.get("time_spent_fraction")
        if fraction is not None:
            if in_book:
                entry["in_book_frac_total"] += fraction
                entry["in_book_frac_count"] += 1
            else:
                entry["out_book_frac_total"] += fraction
                entry["out_book_frac_count"] += 1

    for entry in summary.values():
        entry["in_book_avg"] = (
            entry["in_book_total"] / entry["in_book_count"]
            if entry["in_book_count"]
            else None
        )
        entry["out_book_avg"] = (
            entry["out_book_total"] / entry["out_book_count"]
            if entry["out_book_count"]
            else None
        )
        entry["in_book_frac_avg"] = (
            entry["in_book_frac_total"] / entry["in_book_frac_count"]
            if entry["in_book_frac_count"]
            else None
        )
        entry["out_book_frac_avg"] = (
            entry["out_book_frac_total"] / entry["out_book_frac_count"]
            if entry["out_book_frac_count"]
            else None
        )
    return summary
