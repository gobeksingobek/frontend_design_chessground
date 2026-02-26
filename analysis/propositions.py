from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

PROPOSITION_TYPE_MISSING_COVERAGE_BRANCH = "MISSING_COVERAGE_BRANCH"


def rebuild_missing_coverage_propositions(
    conn: sqlite3.Connection,
    threshold: int,
    resurface_gap: int = 3,
) -> None:
    threshold = max(1, int(threshold))
    resurface_gap = max(1, int(resurface_gap))
    now_iso = datetime.now(timezone.utc).isoformat()

    existing_rows = conn.execute(
        """
        SELECT id, proposition_key, status, dismissed_count, decided_at,
               pos_id, uci_move, detail_json
        FROM review_propositions
        WHERE proposition_type = ?
        """,
        (PROPOSITION_TYPE_MISSING_COVERAGE_BRANCH,),
    ).fetchall()
    existing_by_key = {str(row["proposition_key"]): row for row in existing_rows}

    aggregates = conn.execute(
        """
        SELECT gp.pos_id,
               gp.uci_move,
               p.fen_norm,
               COUNT(DISTINCT m.game_id) AS evidence_count,
               MIN(m.matched_line_id) AS line_id_hint
        FROM matches m
        JOIN game_positions gp
          ON gp.game_id = m.game_id
         AND gp.ply = m.deviation_ply_opp
        JOIN positions p
          ON p.id = gp.pos_id
        WHERE m.compliance = 'MISSING_COVERAGE'
          AND m.deviation_ply_opp IS NOT NULL
        GROUP BY gp.pos_id, gp.uci_move, p.fen_norm
        """
    ).fetchall()

    touched_keys: set[str] = set()
    for row in aggregates:
        pos_id = int(row["pos_id"])
        uci_move = str(row["uci_move"] or "")
        proposition_key = _proposition_key(pos_id, uci_move)
        touched_keys.add(proposition_key)

        evidence_count = int(row["evidence_count"] or 0)
        line_id_hint = row["line_id_hint"]
        detail_json = json.dumps(
            {
                "fen": row["fen_norm"] or "",
                "pos_id": pos_id,
                "uci_move": uci_move,
                "sample_games": _fetch_sample_games(conn, pos_id, uci_move),
            }
        )

        existing = existing_by_key.get(proposition_key)
        if existing is None:
            if evidence_count <= threshold:
                continue
            conn.execute(
                """
                INSERT INTO review_propositions (
                    proposition_type,
                    proposition_key,
                    status,
                    evidence_count,
                    threshold_count,
                    pos_id,
                    uci_move,
                    line_id_hint,
                    detail_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    PROPOSITION_TYPE_MISSING_COVERAGE_BRANCH,
                    proposition_key,
                    evidence_count,
                    threshold,
                    pos_id,
                    uci_move,
                    line_id_hint,
                    detail_json,
                    now_iso,
                    now_iso,
                ),
            )
            continue

        status = str(existing["status"] or "PENDING").upper()
        decided_at = existing["decided_at"]
        if status == "DISAPPROVED":
            dismissed_count = int(existing["dismissed_count"] or 0)
            if evidence_count >= dismissed_count + resurface_gap:
                status = "PENDING"
                decided_at = None

        conn.execute(
            """
            UPDATE review_propositions
            SET status = ?,
                evidence_count = ?,
                threshold_count = ?,
                pos_id = ?,
                uci_move = ?,
                line_id_hint = ?,
                detail_json = ?,
                decided_at = ?,
                updated_at = ?
            WHERE proposition_key = ?
            """,
            (
                status,
                evidence_count,
                threshold,
                pos_id,
                uci_move,
                line_id_hint,
                detail_json,
                decided_at,
                now_iso,
                proposition_key,
            ),
        )

    for proposition_key, existing in existing_by_key.items():
        if proposition_key in touched_keys:
            continue
        conn.execute(
            """
            UPDATE review_propositions
            SET evidence_count = 0,
                threshold_count = ?,
                updated_at = ?
            WHERE proposition_key = ?
            """,
            (threshold, now_iso, proposition_key),
        )

    conn.commit()


def _proposition_key(pos_id: int, uci_move: str) -> str:
    return f"MC|{int(pos_id)}|{uci_move}"


def _fetch_sample_games(
    conn: sqlite3.Connection,
    pos_id: int,
    uci_move: str,
    limit: int = 5,
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT g.id AS game_id,
               g.date,
               g.white,
               g.black,
               g.result,
               m.deviation_ply_opp
        FROM matches m
        JOIN games g
          ON g.id = m.game_id
        JOIN game_positions gp
          ON gp.game_id = m.game_id
         AND gp.ply = m.deviation_ply_opp
        WHERE m.compliance = 'MISSING_COVERAGE'
          AND gp.pos_id = ?
          AND gp.uci_move = ?
        ORDER BY g.date DESC, g.id DESC
        LIMIT ?
        """,
        (int(pos_id), uci_move, int(limit)),
    ).fetchall()
    return [dict(row) for row in rows]
