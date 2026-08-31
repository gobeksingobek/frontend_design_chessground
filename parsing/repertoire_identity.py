from __future__ import annotations

import hashlib


def canonical_path_hash(root_key: str, moves_uci: list[str], side_to_play: str) -> str:
    payload = "|".join([root_key.strip(), side_to_play.strip().lower(), *moves_uci])
    return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()
