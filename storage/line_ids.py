from __future__ import annotations

import base64
import hashlib
import re
import sqlite3


def _normalize_prefix(value: str, fallback: str = "root") -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return cleaned or fallback


def _edge_token(uci_move: str) -> str:
    digest = hashlib.blake2s((uci_move or "").encode("utf-8"), digest_size=5).digest()
    token = base64.b32encode(digest).decode("ascii").lower().rstrip("=")
    return token[:6]


def canonical_path_hash(root_prefix: str, moves_uci: list[str], side_to_play: str) -> str:
    canonical = f"{_normalize_prefix(root_prefix)}|{(side_to_play or 'white').lower()}|{' '.join(moves_uci)}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parent_prefix(root_prefix: str, moves_uci: list[str]) -> str:
    root = _normalize_prefix(root_prefix)
    if not moves_uci:
        return root
    return f"{root}-{'-'.join(_edge_token(move) for move in moves_uci)}"


def allocate_line_id(
    conn: sqlite3.Connection,
    *,
    root_prefix: str,
    moves_uci: list[str],
    side_to_play: str,
) -> tuple[str, str]:
    path_hash = canonical_path_hash(root_prefix, moves_uci, side_to_play)
    existing = conn.execute(
        "SELECT line_id FROM repertoire_lines WHERE canonical_path_hash = ?", (path_hash,)
    ).fetchone()
    if existing:
        return existing["line_id"], path_hash

    parent_prefix = _parent_prefix(root_prefix, moves_uci)
    conn.execute(
        "INSERT OR IGNORE INTO line_id_sequences(parent_prefix, next_sequence) VALUES (?, 1)",
        (parent_prefix,),
    )
    row = conn.execute(
        """
        UPDATE line_id_sequences
        SET next_sequence = next_sequence + 1
        WHERE parent_prefix = ?
        RETURNING next_sequence - 1 AS seq
        """,
        (parent_prefix,),
    ).fetchone()
    seq = int(row["seq"])
    return f"{parent_prefix}-{seq}", path_hash
