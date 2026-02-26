from __future__ import annotations

import sqlite3

from analysis.thresholds import BLUNDER_MIN


def generate_review_items(conn: sqlite3.Connection, top_n: int) -> list[dict]:
    items: list[dict] = []

    rows = conn.execute(
        """
        SELECT m.matched_line_id AS line_id,
               AVG(m.deviation_ply_you) AS avg_self_dev
        FROM matches m
        WHERE m.deviation_ply_you IS NOT NULL
          AND m.matched_line_id IS NOT NULL
        GROUP BY m.matched_line_id
        ORDER BY avg_self_dev ASC
        LIMIT ?
        """,
        (top_n,),
    ).fetchall()
    for row in rows:
        items.append(
            {
                "line_id": row["line_id"],
                "reason": "EARLY_SELF_DEVIATION",
                "detail": f"Avg self deviation ply: {row['avg_self_dev']:.1f}",
            }
        )

    rows = conn.execute(
        """
        SELECT m.matched_line_id AS line_id, COUNT(*) AS count
        FROM matches m
        WHERE m.deviation_ply_opp IS NOT NULL
          AND m.matched_line_id IS NOT NULL
        GROUP BY m.matched_line_id
        HAVING count >= 2
        ORDER BY count DESC
        LIMIT ?
        """,
        (top_n,),
    ).fetchall()
    for row in rows:
        items.append(
            {
                "line_id": row["line_id"],
                "reason": "REPEATED_OPPONENT_DEVIATION",
                "detail": f"Opponent deviations: {row['count']}",
            }
        )

    rows = conn.execute(
        """
        SELECT m.matched_line_id AS line_id,
               SUM(CASE
                     WHEN g.result = '1-0' AND g.player_color = 'white' THEN 1
                     WHEN g.result = '0-1' AND g.player_color = 'black' THEN 1
                     ELSE 0
                   END) AS wins,
               SUM(CASE
                     WHEN g.result = '0-1' AND g.player_color = 'white' THEN 1
                     WHEN g.result = '1-0' AND g.player_color = 'black' THEN 1
                     ELSE 0
                   END) AS losses
        FROM matches m
        JOIN games g ON m.game_id = g.id
        WHERE m.matched_line_id IS NOT NULL
        GROUP BY m.matched_line_id
        HAVING losses > wins
        ORDER BY losses DESC
        LIMIT ?
        """,
        (top_n,),
    ).fetchall()
    for row in rows:
        items.append(
            {
                "line_id": row["line_id"],
                "reason": "POOR_PERFORMANCE",
                "detail": f"Losses {row['losses']} > wins {row['wins']}",
            }
        )

    rows = conn.execute(
        """
        SELECT m.matched_line_id AS line_id,
               AVG(ap.your_cpl) AS avg_cpl
        FROM matches m
        JOIN analysis_ply ap ON m.game_id = ap.game_id AND ap.ply = m.deviation_ply_you
        WHERE m.deviation_ply_you IS NOT NULL
          AND m.matched_line_id IS NOT NULL
        GROUP BY m.matched_line_id
        HAVING avg_cpl >= ?
        ORDER BY avg_cpl DESC
        LIMIT ?
        """,
        (BLUNDER_MIN, top_n),
    ).fetchall()
    for row in rows:
        items.append(
            {
                "line_id": row["line_id"],
                "reason": "EARLY_SELF_HIGH_CPL",
                "detail": f"Avg CPL at deviation: {row['avg_cpl']:.1f}",
            }
        )

    rows = conn.execute(
        """
        SELECT p.fen_norm AS position,
               gp.uci_move,
               COUNT(*) AS count
        FROM game_positions gp
        JOIN positions p ON gp.pos_id = p.id
        JOIN games g ON gp.game_id = g.id
        WHERE gp.is_self = 0 AND gp.repertoire_class = 'OUT_OF_REPERTOIRE'
        GROUP BY gp.pos_id, gp.uci_move
        ORDER BY count DESC
        LIMIT ?
        """,
        (top_n,),
    ).fetchall()
    for row in rows:
        items.append(
            {
                "line_id": None,
                "reason": "MISSING_COVERAGE_HOTSPOT",
                "detail": f"{row['position']} -> {row['uci_move']} ({row['count']})",
            }
        )

    return items


def store_review_items(conn: sqlite3.Connection, items: list[dict]) -> None:
    conn.execute("DELETE FROM review_items")
    rows = [(item.get("line_id"), item["reason"], item["detail"]) for item in items]
    conn.executemany(
        """
        INSERT INTO review_items (line_id, reason, detail)
        VALUES (?, ?, ?)
        """,
        rows,
    )
    conn.commit()
