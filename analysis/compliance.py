from __future__ import annotations

OPPONENT_BLUNDER_CP = 200

def classify_compliance(
    first_opponent_deviation_ply: int | None, first_self_deviation_ply: int | None
) -> str:
    if first_opponent_deviation_ply is None and first_self_deviation_ply is None:
        return "FULLY_COMPLIANT"
    if first_self_deviation_ply is not None and (
        first_opponent_deviation_ply is None
        or first_self_deviation_ply <= first_opponent_deviation_ply
    ):
        return "YOU_DEVIATED"
    return "OPPONENT_DEVIATED"


def classify_opponent_deviation(opponent_eval_delta_cp: int | None) -> str:
    if opponent_eval_delta_cp is None:
        return "OPPONENT_DEVIATED"
    if abs(int(opponent_eval_delta_cp)) < OPPONENT_BLUNDER_CP:
        return "MISSING_COVERAGE"
    return "OPP_BLUNDER"


def classify_compliance_with_completion(
    first_opponent_deviation_ply: int | None,
    first_self_deviation_ply: int | None,
    max_matched_ply: int | None,
    line_len: int | None,
) -> str:
    base = classify_compliance(first_opponent_deviation_ply, first_self_deviation_ply)
    if base != "FULLY_COMPLIANT":
        return base
    matched = int(max_matched_ply or 0)
    required = int(line_len or 0)
    if matched >= required:
        return "FULLY_COMPLIANT"
    return "INCOMPLETE"


def classify_compliance_with_completion_and_eval(
    first_opponent_deviation_ply: int | None,
    first_self_deviation_ply: int | None,
    max_matched_ply: int | None,
    line_len: int | None,
    opponent_eval_delta_cp: int | None,
) -> str:
    base = classify_compliance(first_opponent_deviation_ply, first_self_deviation_ply)
    if base == "YOU_DEVIATED":
        return "YOU_DEVIATED"
    if base == "OPPONENT_DEVIATED":
        return classify_opponent_deviation(opponent_eval_delta_cp)
    matched = int(max_matched_ply or 0)
    required = int(line_len or 0)
    if matched >= required:
        return "FULLY_COMPLIANT"
    return "INCOMPLETE"


def who_left_first(
    first_opponent_deviation_ply: int | None, first_self_deviation_ply: int | None
) -> str:
    if first_opponent_deviation_ply is None and first_self_deviation_ply is None:
        return "NONE"
    if first_opponent_deviation_ply is not None and first_self_deviation_ply is not None:
        if first_opponent_deviation_ply == first_self_deviation_ply:
            return "BOTH"
        return (
            "OPPONENT"
            if first_opponent_deviation_ply < first_self_deviation_ply
            else "YOU"
        )
    if first_self_deviation_ply is not None:
        return "YOU"
    return "OPPONENT"
