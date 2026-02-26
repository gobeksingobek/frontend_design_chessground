from __future__ import annotations

from analysis.thresholds import DEVIATION_WORSE_MIN, REP_MOVE_FINE_MAX, REP_MOVE_INACCURATE_MIN


def repertoire_eval_message(
    your_cpl: int | None,
    rep_cpl: int | None,
    who_left_first: str | None,
) -> str:
    if who_left_first == "OPPONENT":
        return "Opponent deviation made the line irrelevant."
    if your_cpl is None or rep_cpl is None:
        return ""

    rep_vs_best = max(0, your_cpl - rep_cpl)
    if rep_vs_best <= REP_MOVE_FINE_MAX:
        return "Repertoire move is still fine."
    if rep_vs_best >= REP_MOVE_INACCURATE_MIN:
        return "Repertoire move is inaccurate here."
    if rep_cpl >= DEVIATION_WORSE_MIN:
        return "You deviated into a worse line."
    return ""
