from __future__ import annotations

import hashlib


def compute_game_hash(tags: dict, moves_uci: list[str]) -> str:
    hasher = hashlib.sha1()
    hasher.update(
        "|".join(
            [
                tags.get("Event", ""),
                tags.get("Site", ""),
                tags.get("Date", ""),
                tags.get("White", ""),
                tags.get("Black", ""),
                tags.get("Result", ""),
            ]
        ).encode("utf-8", errors="ignore")
    )
    hasher.update("|".join(moves_uci).encode("utf-8", errors="ignore"))
    return hasher.hexdigest()
