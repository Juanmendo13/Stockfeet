#!/usr/bin/env python
"""Stream a Lichess monthly .pgn.zst into a compact human-move book (no full decompress).

Example:
  python -u scripts/import_lichess_games_book.py ^
    --input \"%USERPROFILE%\\Downloads\\lichess_db_standard_rated_2026-07.pgn.zst\" ^
    --max-games 400000
"""

from __future__ import annotations

import argparse
import io
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

import chess
import chess.pgn
import chess.polyglot
import zstandard as zstd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "stockfeet" / "data" / "human_book.sqlite"
DEFAULT_IN = Path.home() / "Downloads" / "lichess_db_standard_rated_2026-07.pgn.zst"


def elo_band(elo: int) -> int:
    elo = max(700, min(2300, int(elo)))
    return int(round(elo / 200) * 200)


def zobrist_i64(board: chess.Board) -> int:
    """Polyglot hash as signed 64-bit for SQLite INTEGER."""
    z = chess.polyglot.zobrist_hash(board) & 0xFFFFFFFFFFFFFFFF
    return z - 0x10000000000000000 if z >= 0x8000000000000000 else z


def parse_elo(headers: chess.pgn.Headers, key: str) -> int | None:
    raw = headers.get(key, "")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def time_control_ok(tc: str) -> bool:
    """Keep blitz/rapid/classical; skip ultraBullet-ish."""
    if not tc or tc == "-":
        return False
    # Formats like 60+0, 180+2, 600+0
    try:
        base = tc.split("+")[0]
        seconds = int(base)
    except ValueError:
        return "bullet" not in tc.lower()
    return seconds >= 180  # 3+0 and slower (more deliberate play)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS moves (
            zobrist INTEGER NOT NULL,
            band INTEGER NOT NULL,
            uci TEXT NOT NULL,
            n INTEGER NOT NULL,
            PRIMARY KEY (zobrist, band, uci)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.commit()


def flush(conn: sqlite3.Connection, bucket: dict[tuple[int, int, str], int]) -> None:
    if not bucket:
        return
    conn.executemany(
        """
        INSERT INTO moves(zobrist, band, uci, n) VALUES (?, ?, ?, ?)
        ON CONFLICT(zobrist, band, uci) DO UPDATE SET n = n + excluded.n
        """,
        [(z, b, u, n) for (z, b, u), n in bucket.items()],
    )
    conn.commit()
    bucket.clear()


def import_stream(
    *,
    input_path: Path,
    output_path: Path,
    max_games: int,
    max_ply: int,
    flush_every: int,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    conn = sqlite3.connect(output_path)
    ensure_schema(conn)
    bucket: dict[tuple[int, int, str], int] = defaultdict(int)

    dctx = zstd.ZstdDecompressor()
    games = 0
    kept = 0
    moves_recorded = 0
    t0 = time.time()

    print(f"Streaming {input_path}", flush=True)
    print(f"Writing  {output_path}", flush=True)
    print(f"Limits: max_games={max_games:,} max_ply={max_ply}", flush=True)

    with input_path.open("rb") as fh, dctx.stream_reader(fh) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
        while games < max_games:
            game = chess.pgn.read_game(text)
            if game is None:
                break
            games += 1

            if games % 2000 == 0:
                elapsed = max(1.0, time.time() - t0)
                print(
                    f"  scanned {games:,} games · kept {kept:,} · "
                    f"move-events {moves_recorded:,} · {games / elapsed:.0f} g/s",
                    flush=True,
                )
                flush(conn, bucket)

            headers = game.headers
            if headers.get("Event", "").find("Rated") < 0 and "Rated" not in headers.get("Event", ""):
                # Monthly DB is already rated standard; still check TC.
                pass
            if not time_control_ok(headers.get("TimeControl", "")):
                continue
            white_elo = parse_elo(headers, "WhiteElo")
            black_elo = parse_elo(headers, "BlackElo")
            if white_elo is None or black_elo is None:
                continue
            if min(white_elo, black_elo) < 700 or max(white_elo, black_elo) > 2400:
                continue

            board = game.board()
            ply = 0
            node = game
            used = False
            while node.variations and ply < max_ply:
                next_node = node.variation(0)
                move = next_node.move
                stm_elo = white_elo if board.turn == chess.WHITE else black_elo
                band = elo_band(stm_elo)
                z = zobrist_i64(board)
                bucket[(z, band, move.uci())] += 1
                moves_recorded += 1
                board.push(move)
                node = next_node
                ply += 1
                used = True

            if used:
                kept += 1

            if len(bucket) >= flush_every:
                flush(conn, bucket)

    flush(conn, bucket)

    print("Pruning rare rows (n < 3)…", flush=True)
    deleted = conn.execute("DELETE FROM moves WHERE n < 3").rowcount
    conn.commit()
    conn.execute("VACUUM")
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('source', ?)",
        (str(input_path),),
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('games_scanned', ?)",
        (str(games),),
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('games_kept', ?)",
        (str(kept),),
    )
    conn.commit()

    rows = conn.execute("SELECT COUNT(*) FROM moves").fetchone()[0]
    pos = conn.execute("SELECT COUNT(DISTINCT zobrist) FROM moves").fetchone()[0]
    size_mb = output_path.stat().st_size / (1024 * 1024)
    conn.close()
    print(
        f"Done. scanned={games:,} kept={kept:,} pruned_rows={deleted:,} "
        f"book_rows={rows:,} positions={pos:,} size={size_mb:.1f} MB",
        flush=True,
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=DEFAULT_IN)
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    p.add_argument("--max-games", type=int, default=400_000)
    p.add_argument("--max-ply", type=int, default=24, help="Plies per game to record")
    p.add_argument("--flush-every", type=int, default=50_000)
    args = p.parse_args()

    if not args.input.exists():
        print(f"Missing input: {args.input}", file=sys.stderr)
        return 1
    import_stream(
        input_path=args.input,
        output_path=args.output,
        max_games=args.max_games,
        max_ply=args.max_ply,
        flush_every=args.flush_every,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
