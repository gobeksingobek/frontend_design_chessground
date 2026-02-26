from __future__ import annotations

import json
import sqlite3


def _safe_int(value) -> int:
    return int(value) if value is not None else 0


def generate_insights(
    conn: sqlite3.Connection,
    top_n: int,
    tabiya_top_n: int,
) -> list[dict]:
    insights: list[dict] = []

    total_positions = _safe_int(
        conn.execute("SELECT COUNT(DISTINCT pos_id) FROM game_positions").fetchone()[0]
    )
    covered_positions = _safe_int(
        conn.execute(
            """
            SELECT COUNT(DISTINCT gp.pos_id)
            FROM game_positions gp
            JOIN line_positions lp ON gp.pos_id = lp.pos_id
            """
        ).fetchone()[0]
    )
    if total_positions:
        coverage_pct = (covered_positions / total_positions) * 100
        details = (
            f"{coverage_pct:.1f}% of positions reached in games are in the repertoire "
            f"({covered_positions}/{total_positions})."
        )
    else:
        details = "No game positions found yet."
    insights.append(
        {
            "category": "Coverage",
            "title": "Repertoire coverage rate",
            "details": details,
            "data": {
                "total_positions": total_positions,
                "covered_positions": covered_positions,
            },
        }
    )

    row = conn.execute(
        """
        SELECT
            SUM(CASE WHEN lp.pos_id IS NOT NULL THEN 1 ELSE 0 END) AS covered,
            SUM(CASE WHEN lp.pos_id IS NULL THEN 1 ELSE 0 END) AS uncovered
        FROM game_positions gp
        LEFT JOIN game_positions gp2
          ON gp2.game_id = gp.game_id AND gp2.ply = gp.ply + 1
        LEFT JOIN line_positions lp ON lp.pos_id = gp2.pos_id
        WHERE gp.is_self = 0 AND gp.repertoire_class = 'OUT_OF_REPERTOIRE'
        """
    ).fetchone()
    covered_dev = _safe_int(row["covered"])
    uncovered_dev = _safe_int(row["uncovered"])
    total_dev = covered_dev + uncovered_dev
    if total_dev:
        details = (
            f"Opponent deviations that land in a known position: {covered_dev} | "
            f"uncovered: {uncovered_dev}."
        )
    else:
        details = "No opponent deviations recorded."
    insights.append(
        {
            "category": "Coverage",
            "title": "Opponent deviations covered",
            "details": details,
            "data": {"covered": covered_dev, "uncovered": uncovered_dev},
        }
    )

    rows = conn.execute(
        """
        SELECT p.fen_norm, gp.uci_move, COUNT(*) AS count
        FROM game_positions gp
        JOIN positions p ON gp.pos_id = p.id
        LEFT JOIN game_positions gp2
          ON gp2.game_id = gp.game_id AND gp2.ply = gp.ply + 1
        LEFT JOIN line_positions lp ON lp.pos_id = gp2.pos_id
        WHERE gp.is_self = 0
          AND gp.repertoire_class = 'OUT_OF_REPERTOIRE'
          AND lp.pos_id IS NULL
        GROUP BY gp.pos_id, gp.uci_move
        ORDER BY count DESC
        LIMIT ?
        """,
        (top_n,),
    ).fetchall()
    hotspot_list = [
        {"fen": row["fen_norm"], "move": row["uci_move"], "count": row["count"]}
        for row in rows
    ]
    details = (
        ", ".join(
            f"{item['move']} ({item['count']}) @ {item['fen']}" for item in hotspot_list
        )
        if hotspot_list
        else "No uncovered opponent hotspots yet."
    )
    insights.append(
        {
            "category": "Coverage",
            "title": "Top uncovered opponent deviations",
            "details": details,
            "data": hotspot_list,
        }
    )

    rows = conn.execute(
        """
        SELECT p.fen_norm, gp.uci_move, COUNT(*) AS count
        FROM game_positions gp
        JOIN positions p ON gp.pos_id = p.id
        WHERE gp.is_self = 1 AND gp.repertoire_class = 'OUT_OF_REPERTOIRE'
        GROUP BY gp.pos_id, gp.uci_move
        ORDER BY count DESC
        LIMIT ?
        """,
        (top_n,),
    ).fetchall()
    self_dev_list = [
        {"fen": row["fen_norm"], "move": row["uci_move"], "count": row["count"]}
        for row in rows
    ]
    details = (
        ", ".join(
            f"{item['move']} ({item['count']}) @ {item['fen']}" for item in self_dev_list
        )
        if self_dev_list
        else "No self deviations recorded."
    )
    insights.append(
        {
            "category": "Deviations",
            "title": "Your most common deviations",
            "details": details,
            "data": self_dev_list,
        }
    )

    rows = conn.execute(
        """
        SELECT matched_line_id AS line_id,
               SUM(CASE WHEN compliance = 'FULLY_COMPLIANT' THEN 1 ELSE 0 END) AS compliant,
               COUNT(*) AS total
        FROM matches
        WHERE matched_line_id IS NOT NULL
        GROUP BY matched_line_id
        HAVING total >= 2
        ORDER BY CAST(compliant AS REAL) / total ASC
        LIMIT ?
        """,
        (top_n,),
    ).fetchall()
    low_comp_list = [
        {
            "line_id": row["line_id"],
            "rate": (row["compliant"] / row["total"] if row["total"] else 0),
            "total": row["total"],
        }
        for row in rows
    ]
    details = (
        ", ".join(
            f"{item['line_id']} ({item['rate']*100:.0f}%, {item['total']})"
            for item in low_comp_list
        )
        if low_comp_list
        else "No line compliance data yet."
    )
    insights.append(
        {
            "category": "Performance",
            "title": "Lowest compliance lines",
            "details": details,
            "data": low_comp_list,
        }
    )

    row = conn.execute(
        """
        SELECT deviation_ply_you AS ply, COUNT(*) AS count
        FROM matches
        WHERE deviation_ply_you IS NOT NULL
        GROUP BY deviation_ply_you
        ORDER BY count DESC
        LIMIT 1
        """
    ).fetchone()
    if row:
        details = f"Most common self deviation ply: {row['ply']} ({row['count']} games)."
    else:
        details = "No self deviation ply data yet."
    insights.append(
        {
            "category": "Deviations",
            "title": "Most common self deviation ply",
            "details": details,
            "data": {"ply": row["ply"], "count": row["count"]} if row else {},
        }
    )

    row = conn.execute(
        """
        SELECT SUM(slow_in_book) AS slow,
               SUM(instant_out_of_book) AS instant,
               SUM(blunder_cluster) AS cluster,
               COUNT(*) AS total
        FROM time_patterns
        """
    ).fetchone()
    slow = _safe_int(row["slow"])
    instant = _safe_int(row["instant"])
    cluster = _safe_int(row["cluster"])
    total = _safe_int(row["total"])
    if total:
        details = (
            f"Slow in-book: {slow} | Instant out-of-book: {instant} | "
            f"Blunder clusters after leaving book: {cluster}."
        )
    else:
        details = "No time pattern data yet."
    insights.append(
        {
            "category": "Time",
            "title": "Time pattern counts",
            "details": details,
            "data": {
                "slow_in_book": slow,
                "instant_out_of_book": instant,
                "blunder_cluster": cluster,
                "total": total,
            },
        }
    )

    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM matches
        WHERE tags_json LIKE '%BLUNDER_LIKE%'
        """
    ).fetchone()
    blunder_like = _safe_int(row["count"])
    details = (
        f"Blunder-like deviations flagged: {blunder_like}."
        if blunder_like
        else "No blunder-like deviations flagged."
    )
    insights.append(
        {
            "category": "Performance",
            "title": "Blunder-like deviations",
            "details": details,
            "data": {"count": blunder_like},
        }
    )

    rows = conn.execute(
        """
        SELECT p.fen_norm, COUNT(*) AS count
        FROM game_positions gp
        JOIN positions p ON gp.pos_id = p.id
        GROUP BY gp.pos_id
        ORDER BY count DESC
        LIMIT ?
        """,
        (tabiya_top_n,),
    ).fetchall()
    tabiya_list = [
        {"fen": row["fen_norm"], "count": row["count"]} for row in rows
    ]
    details = (
        ", ".join(f"{item['count']}x @ {item['fen']}" for item in tabiya_list)
        if tabiya_list
        else "No positions recorded yet."
    )
    insights.append(
        {
            "category": "Coverage",
            "title": "Most frequent positions reached",
            "details": details,
            "data": tabiya_list,
        }
    )

    return insights


def store_insights(conn: sqlite3.Connection, insights: list[dict]) -> None:
    conn.execute("DELETE FROM insights")
    rows = []
    for insight in insights:
        data = insight.get("data")
        data_json = json.dumps(data) if data is not None else None
        rows.append(
            (
                insight.get("category"),
                insight.get("title"),
                insight.get("details"),
                data_json,
            )
        )

    conn.executemany(
        """
        INSERT INTO insights (category, title, details, data_json)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
