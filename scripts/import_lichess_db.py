"""Import local Lichess puzzle DB (.csv.zst) into Stockfeet SQLite.

Default source: C:\\Proyectos\\Stockfeet\\data\\lichess_db_puzzle.csv.zst
Output: stockfeet/data/puzzles.sqlite
"""

from __future__ import annotations

import csv
import io
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import chess
import zstandard as zstd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "data" / "lichess_db_puzzle.csv.zst"
OUT = ROOT / "stockfeet" / "data" / "puzzles.sqlite"

# Keep a large but practical library (not all 3M+ rows).
MAX_PER_100_ELO = 2000
MIN_POPULARITY = 88
MIN_PLAYS = 400
MAX_RD = 85


def band_key(rating: int) -> int:
    return (rating // 100) * 100


def convert(fen: str, moves: list[str]) -> tuple[str, list[str]] | None:
    if len(moves) < 2:
        return None
    try:
        board = chess.Board(fen)
        first = chess.Move.from_uci(moves[0])
        if first not in board.legal_moves:
            return None
        board.push(first)
        for uci in moves[1:]:
            m = chess.Move.from_uci(uci)
            if m not in board.legal_moves:
                return None
            board.push(m)
    except ValueError:
        return None
    start = chess.Board(fen)
    start.push(chess.Move.from_uci(moves[0]))
    return start.fen(), moves[1:]


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    if not src.exists():
        print(f"Missing source: {src}")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()

    conn = sqlite3.connect(OUT)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE puzzles (
            id TEXT PRIMARY KEY,
            rating INTEGER NOT NULL,
            themes TEXT NOT NULL,
            fen TEXT NOT NULL,
            solution TEXT NOT NULL,
            title TEXT NOT NULL,
            hint TEXT NOT NULL,
            plays INTEGER NOT NULL,
            popularity INTEGER NOT NULL
        )
        """
    )
    cur.execute("CREATE INDEX idx_puzzles_rating ON puzzles(rating)")
    cur.execute("CREATE INDEX idx_puzzles_themes ON puzzles(themes)")

    counts: dict[int, int] = defaultdict(int)
    scanned = kept = skipped = 0

    print(f"Importing from {src}")
    print(f"Writing {OUT}")

    with src.open("rb") as fh:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(fh) as reader:
            text = io.TextIOWrapper(reader, encoding="utf-8")
            for row in csv.DictReader(text):
                scanned += 1
                if scanned % 250_000 == 0:
                    print(f"  scanned {scanned:,} · kept {kept:,}", flush=True)

                try:
                    rating = int(float(row["Rating"]))
                    popularity = int(float(row["Popularity"]))
                    plays = int(float(row["NbPlays"]))
                    rd = float(row["RatingDeviation"])
                except (KeyError, ValueError):
                    skipped += 1
                    continue

                if popularity < MIN_POPULARITY or plays < MIN_PLAYS or rd > MAX_RD:
                    continue
                if rating < 550 or rating > 2800:
                    continue

                bk = band_key(rating)
                if counts[bk] >= MAX_PER_100_ELO:
                    continue

                moves = row["Moves"].split()
                converted = convert(row["FEN"], moves)
                if converted is None:
                    skipped += 1
                    continue
                fen, solution = converted
                themes = row.get("Themes") or ""
                pid = row["PuzzleId"]
                cur.execute(
                    """
                    INSERT OR IGNORE INTO puzzles
                    (id, rating, themes, fen, solution, title, hint, plays, popularity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"lichess-{pid}",
                        rating,
                        themes,
                        fen,
                        " ".join(solution),
                        f"Lichess {pid} · {rating}",
                        f"Themes: {', '.join(themes.split()[:5])}" if themes else "Find the best idea.",
                        plays,
                        popularity,
                    ),
                )
                if cur.rowcount:
                    counts[bk] += 1
                    kept += 1

    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM puzzles").fetchone()[0]
    mn, mx = cur.execute("SELECT MIN(rating), MAX(rating) FROM puzzles").fetchone()
    conn.close()

    print(f"Done. scanned={scanned:,} kept={kept:,} skipped_illegal={skipped:,}")
    print(f"DB rows={total:,} rating range={mn}-{mx}")
    for bk in sorted(counts):
        print(f"  {bk}-{bk+99}: {counts[bk]}")
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main())
