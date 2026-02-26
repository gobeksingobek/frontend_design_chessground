from __future__ import annotations

import re
from typing import Tuple

CLOCK_RE = re.compile(r"\[%clk\s+([0-9:.]+)\]")
TIME_CONTROL_RE = re.compile(r"^(\d+)(?:\+(\d+))?$")


def parse_clock_seconds(comment: str | None) -> float | None:
    if not comment:
        return None
    match = CLOCK_RE.search(comment)
    if not match:
        return None
    value = match.group(1)
    parts = value.split(":")
    if len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        return None
    try:
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError:
        return None


def parse_time_control(time_control: str | None) -> Tuple[int | None, int | None]:
    if not time_control:
        return None, None
    match = TIME_CONTROL_RE.match(time_control.strip())
    if not match:
        return None, None
    base = int(match.group(1))
    increment = int(match.group(2)) if match.group(2) else 0
    return base, increment


def compute_time_spent(
    prev_clock: float | None, current_clock: float | None, increment: int | None
) -> float | None:
    if current_clock is None or prev_clock is None:
        return None
    increment = increment or 0
    spent = prev_clock - current_clock + increment
    if spent < 0:
        return 0.0
    return spent
