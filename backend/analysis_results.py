from __future__ import annotations

import json

import asyncpg

from backend.settings import SETTINGS


def _quality(cpl: int | None) -> str | None:
    if cpl is None:
        return None
    if cpl <= 20:
        return "excellent"
    if cpl <= 50:
        return "good"
    if cpl <= 100:
        return "inaccuracy"
    if cpl <= 200:
        return "mistake"
    return "blunder"


async def _regenerate_review_outputs(
    conn: asyncpg.Connection, workspace_id: str, analysis_run_id: str
) -> None:
    threshold = await conn.fetchval(
        """
        SELECT COALESCE((payload->>'missing_coverage_proposal_threshold')::int, 5)
        FROM runtime_settings WHERE workspace_id=$1::uuid
        """,
        workspace_id,
    )
    await conn.execute(
        """
        INSERT INTO review_propositions(
            workspace_id, proposition_type, proposition_key, status,
            evidence_count, threshold_count, pos_id, uci_move, line_id_hint,
            evidence_json, detail_json, updated_at
        )
        SELECT $1::uuid, 'MISSING_COVERAGE_BRANCH',
               format('%s:%s', gp.pos_id, gp.uci_move), 'PENDING',
               COUNT(*)::int, $3, gp.pos_id, gp.uci_move,
               MIN(match.matched_line_id),
               jsonb_build_object('game_ids', jsonb_agg(match.game_id ORDER BY match.game_id)),
               jsonb_build_object('analysis_run_id', $2::text), NOW()
        FROM matches match
        JOIN game_positions gp
          ON gp.workspace_id=match.workspace_id AND gp.game_id=match.game_id
         AND gp.ply=match.deviation_ply_opp
        WHERE match.workspace_id=$1::uuid AND match.analysis_run_id=$2::uuid
          AND match.deviation_ply_opp IS NOT NULL AND gp.uci_move IS NOT NULL
        GROUP BY gp.pos_id, gp.uci_move
        ON CONFLICT (workspace_id, proposition_key) DO UPDATE
        SET evidence_count=EXCLUDED.evidence_count,
            threshold_count=EXCLUDED.threshold_count,
            pos_id=EXCLUDED.pos_id,
            uci_move=EXCLUDED.uci_move,
            line_id_hint=EXCLUDED.line_id_hint,
            evidence_json=EXCLUDED.evidence_json,
            detail_json=EXCLUDED.detail_json,
            status=CASE
                WHEN review_propositions.status='DISAPPROVED'
                 AND EXCLUDED.evidence_count > review_propositions.dismissed_count
                THEN 'PENDING'
                ELSE review_propositions.status
            END,
            updated_at=NOW()
        """,
        workspace_id, analysis_run_id, int(threshold or 5),
    )
    await conn.execute(
        "DELETE FROM review_items WHERE workspace_id=$1::uuid AND analysis_run_id=$2::uuid",
        workspace_id, analysis_run_id,
    )
    await conn.execute(
        """
        INSERT INTO review_items(workspace_id, analysis_run_id, line_id, reason, detail)
        SELECT $1::uuid, $2::uuid, match.matched_line_id, 'high-cpl',
               format('Game %s contains a %s CPL move at ply %s.', ap.game_id, ap.your_cpl, ap.ply)
        FROM analysis_ply ap
        LEFT JOIN matches match
          ON match.workspace_id=ap.workspace_id AND match.game_id=ap.game_id
         AND match.analysis_run_id=ap.analysis_run_id
        WHERE ap.workspace_id=$1::uuid AND ap.analysis_run_id=$2::uuid AND ap.your_cpl >= 100
        ORDER BY ap.your_cpl DESC NULLS LAST
        LIMIT 100
        """,
        workspace_id, analysis_run_id,
    )
    await conn.execute(
        """
        UPDATE trainer_line_state state
        SET auto_priority_score = summary.score,
            needs_review = CASE WHEN summary.score > 0 THEN 1 ELSE state.needs_review END
        FROM (
            SELECT match.matched_line_id AS line_id, COUNT(*)::int AS score
            FROM matches match
            WHERE match.workspace_id=$1::uuid AND match.analysis_run_id=$2::uuid
              AND match.compliance <> 'FULLY_COMPLIANT' AND match.matched_line_id IS NOT NULL
            GROUP BY match.matched_line_id
        ) summary
        WHERE state.workspace_id=$1::uuid AND state.line_id=summary.line_id
        """,
        workspace_id, analysis_run_id,
    )
    await conn.execute(
        "DELETE FROM insights WHERE workspace_id=$1::uuid AND analysis_run_id=$2::uuid",
        workspace_id, analysis_run_id,
    )
    await conn.execute(
        """
        INSERT INTO insights(workspace_id, analysis_run_id, category, title, details, data_json)
        SELECT $1::uuid, $2::uuid, 'summary', 'Analysis completed',
               format('%s games and %s evaluated plies are active.', COUNT(DISTINCT game_id), COUNT(*)),
               jsonb_build_object('games', COUNT(DISTINCT game_id), 'plies', COUNT(*))
        FROM analysis_ply WHERE workspace_id=$1::uuid AND analysis_run_id=$2::uuid
        """,
        workspace_id, analysis_run_id,
    )


async def finalize_analysis_run(conn: asyncpg.Connection, job_id: str) -> None:
    job = await conn.fetchrow("SELECT * FROM analysis_jobs WHERE id = $1::uuid", job_id)
    if job is None:
        return
    workspace_id = str(job["workspace_id"])
    if str(job["job_type"]) == "review-insight-regeneration":
        active_run_id = await conn.fetchval(
            "SELECT active_analysis_run_id FROM workspace_state WHERE workspace_id=$1::uuid",
            workspace_id,
        )
        if active_run_id is None:
            raise RuntimeError("Review regeneration requires a completed active analysis run.")
        await _regenerate_review_outputs(conn, workspace_id, str(active_run_id))
        return
    if not str(job["job_type"]).endswith("analysis") and "reanalysis" not in str(job["job_type"]):
        return
    request_payload = job["request_json"] or {}
    if isinstance(request_payload, str):
        request_payload = json.loads(request_payload)
    settings_snapshot = request_payload.get("settings_snapshot") or {}
    analysis_depth = int(settings_snapshot.get("engine_depth") or SETTINGS.stockfish_depth)
    max_plies = int(settings_snapshot.get("max_plies") or 30)
    engine_profile = request_payload.get("engine_profile") or {}
    engine_id = str(engine_profile.get("engine_id") or SETTINGS.stockfish_engine_id)
    game_ids = [int(value) for value in request_payload.get("game_ids_snapshot", [])]
    rows = await conn.fetch(
        """
        SELECT gp.game_id, gp.ply, gp.pos_id, gp.is_self, game.player_color,
               match.max_matched_ply,
               pre_cache.eval_cp AS pre_eval_cp, pre_cache.best_uci,
               post_cache.eval_cp AS post_eval_cp
        FROM game_positions gp
        JOIN games game ON game.id = gp.game_id AND game.workspace_id = gp.workspace_id
        LEFT JOIN matches match ON match.workspace_id=gp.workspace_id
                               AND match.game_id=gp.game_id
                               AND match.analysis_run_id=$5::uuid
        LEFT JOIN engine_cache pre_cache
          ON pre_cache.pos_id = gp.pos_id AND pre_cache.depth = $2 AND pre_cache.engine_id = $3
         AND pre_cache.mode = 'fixed' AND pre_cache.max_time_ms=0 AND pre_cache.options_hash = ''
        LEFT JOIN engine_cache post_cache
          ON post_cache.pos_id = gp.next_pos_id AND post_cache.depth = $2 AND post_cache.engine_id = $3
         AND post_cache.mode = 'fixed' AND post_cache.max_time_ms=0 AND post_cache.options_hash = ''
        WHERE gp.workspace_id = $1::uuid AND gp.game_id=ANY($4::bigint[]) AND gp.ply <= $6
        ORDER BY gp.game_id, gp.ply
        """,
        workspace_id,
        analysis_depth,
        engine_id,
        game_ids,
        job_id,
        max_plies,
    )
    await conn.execute(
        "DELETE FROM analysis_ply WHERE workspace_id = $1::uuid AND analysis_run_id = $2::uuid",
        workspace_id,
        job_id,
    )
    for row in rows:
        game_id = int(row["game_id"])
        pre_eval = row["pre_eval_cp"]
        post_eval = row["post_eval_cp"]
        cpl = None
        if row["is_self"] and pre_eval is not None and post_eval is not None:
            pre_value, post_value = int(pre_eval), int(post_eval)
            cpl = (
                max(0, pre_value - post_value)
                if row["player_color"] == "white"
                else max(0, post_value - pre_value)
            )
        await conn.execute(
            """
            INSERT INTO analysis_ply(
                workspace_id, game_id, analysis_run_id, ply, pos_id,
                pre_eval_cp, post_eval_cp, best_uci, your_cpl, quality_label,
                repertoire_class
            ) VALUES ($1::uuid, $2, $3::uuid, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (workspace_id, analysis_run_id, game_id, ply) DO UPDATE SET
                pre_eval_cp = EXCLUDED.pre_eval_cp,
                post_eval_cp = EXCLUDED.post_eval_cp,
                best_uci = EXCLUDED.best_uci,
                your_cpl = EXCLUDED.your_cpl,
                quality_label = EXCLUDED.quality_label,
                repertoire_class = EXCLUDED.repertoire_class
            """,
            workspace_id, game_id, job_id, row["ply"], row["pos_id"],
            pre_eval, post_eval, row["best_uci"], cpl, _quality(cpl),
            (
                "IN_REPERTOIRE_MAIN"
                if row["max_matched_ply"] is not None
                and int(row["ply"]) <= int(row["max_matched_ply"])
                else "OUT_OF_REPERTOIRE"
            ),
        )
    await conn.execute(
        "DELETE FROM time_patterns WHERE workspace_id = $1::uuid AND analysis_run_id = $2::uuid",
        workspace_id,
        job_id,
    )
    await conn.execute(
        """
        INSERT INTO time_patterns(
            workspace_id, game_id, analysis_run_id, slow_in_book,
            instant_out_of_book, blunder_cluster, details_json
        )
        SELECT gp.workspace_id, gp.game_id, $2::uuid,
               CASE WHEN COUNT(*) FILTER (
                    WHERE ap.repertoire_class IN ('IN_REPERTOIRE_MAIN','IN_REPERTOIRE_OTHER')
                      AND gp.time_spent_seconds >= 30
               ) > 0 THEN 1 ELSE 0 END,
               CASE WHEN COUNT(*) FILTER (
                    WHERE ap.repertoire_class = 'OUT_OF_REPERTOIRE'
                      AND gp.time_spent_seconds <= 2
               ) > 0 THEN 1 ELSE 0 END,
               CASE WHEN COUNT(*) FILTER (WHERE ap.your_cpl >= 200) >= 2 THEN 1 ELSE 0 END,
               jsonb_build_object('analyzed_plies', COUNT(ap.ply))
        FROM game_positions gp
        LEFT JOIN analysis_ply ap
          ON ap.workspace_id=gp.workspace_id AND ap.game_id=gp.game_id
         AND ap.ply=gp.ply AND ap.analysis_run_id=$2::uuid
        WHERE gp.workspace_id=$1::uuid AND gp.game_id=ANY($3::bigint[])
        GROUP BY gp.workspace_id, gp.game_id
        """,
        workspace_id,
        job_id,
        game_ids,
    )
    await _regenerate_review_outputs(conn, workspace_id, job_id)
    await conn.execute(
        """
        INSERT INTO workspace_state(workspace_id, active_analysis_run_id, updated_at)
        VALUES ($1::uuid, $2::uuid, NOW())
        ON CONFLICT (workspace_id) DO UPDATE
        SET active_analysis_run_id = EXCLUDED.active_analysis_run_id, updated_at = NOW()
        """,
        workspace_id,
        job_id,
    )
