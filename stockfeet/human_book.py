from __future__ import annotations

import random
import sqlite3
from pathlib import Path

import chess
import chess.polyglot


def _book_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "human_book.sqlite"


def has_human_book() -> bool:
    return _book_path().exists()


def elo_band(elo: int) -> int:
    """Snap to 200-Elo bands centered for lookup (800, 1000, …, 2200)."""
    elo = max(700, min(2300, int(elo)))
    return int(round(elo / 200) * 200)


def zobrist_i64(board: chess.Board) -> int:
    """Polyglot hash as signed 64-bit for SQLite INTEGER."""
    z = chess.polyglot.zobrist_hash(board) & 0xFFFFFFFFFFFFFFFF
    return z - 0x10000000000000000 if z >= 0x8000000000000000 else z


def pick_book_move(
    board: chess.Board,
    target_elo: int,
    *,
    min_count: int = 4,
    rng: random.Random | None = None,
) -> chess.Move | None:
    """Sample a real Lichess human move near target_elo, if the book knows this position."""
    if not has_human_book():
        return None
    rng = rng or random.Random()
    z = zobrist_i64(board)
    legal = {m.uci(): m for m in board.legal_moves}
    if not legal:
        return None

    band = elo_band(target_elo)
    bands = [band, band - 200, band + 200, band - 400, band + 400]
    bands = [b for b in bands if 600 <= b <= 2400]

    with sqlite3.connect(_book_path()) as conn:
        for b in bands:
            rows = conn.execute(
                "SELECT uci, n FROM moves WHERE zobrist=? AND band=? AND n>=?",
                (z, b, min_count if b == band else max(2, min_count // 2)),
            ).fetchall()
            choices = [(uci, n) for uci, n in rows if uci in legal]
            if not choices:
                continue
            total = sum(n for _, n in choices)
            if total < min_count:
                continue
            r = rng.randrange(total)
            acc = 0
            for uci, n in choices:
                acc += n
                if r < acc:
                    return legal[uci]
    return None


def book_stats() -> dict[str, int]:
    if not has_human_book():
        return {"rows": 0, "positions": 0}
    with sqlite3.connect(_book_path()) as conn:
        rows = int(conn.execute("SELECT COUNT(*) FROM moves").fetchone()[0])
        positions = int(conn.execute("SELECT COUNT(DISTINCT zobrist) FROM moves").fetchone()[0])
    return {"rows": rows, "positions": positions}
