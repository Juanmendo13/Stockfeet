"""Build Stockfeet puzzle pack from chess-puzzles-api (Lichess data) + local validation."""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import chess

OUT = Path(__file__).resolve().parents[1] / "stockfeet" / "data" / "puzzles.json"
BASE = "https://chess-puzzles-api.vercel.app/puzzles"
UA = {"User-Agent": "Stockfeet/0.1", "Accept": "application/json"}

BANDS = [
    (600, 900, 45),
    (900, 1100, 45),
    (1100, 1300, 45),
    (1300, 1500, 45),
    (1500, 1700, 40),
    (1700, 1900, 35),
    (1900, 2100, 30),
    (2100, 2500, 25),
]


def convert(row: dict) -> dict | None:
    fen = row["FEN"].replace("\\/", "/")
    moves = row["Moves"].split()
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
    rating = int(row["Rating"])
    themes = str(row.get("Themes") or "").split()
    popularity = int(row.get("Popularity") or 0)
    plays = int(row.get("NbPlays") or 0)
    if popularity < 70 or plays < 50:
        return None
    return {
        "id": f"lichess-{row['PuzzleId']}",
        "lichess_id": row["PuzzleId"],
        "rating": rating,
        "themes": themes,
        "fen": start.fen(),
        "solution": moves[1:],
        "title": f"Lichess {row['PuzzleId']} · {rating}",
        "hint": f"Themes: {', '.join(themes[:5])}" if themes else "Find the best continuation.",
        "source": "lichess",
        "plays": plays,
        "popularity": popularity,
    }


def fetch_band(lo: int, hi: int, limit: int, start: int = 0) -> list[dict]:
    url = f"{BASE}?start={start}&limit={limit}&min_rating={lo}&max_rating={hi}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def main() -> int:
    buckets: list[list[dict]] = [[] for _ in BANDS]
    seen: set[str] = set()

    for i, (lo, hi, need) in enumerate(BANDS):
        print(f"Fetching {lo}-{hi}…", flush=True)
        try:
            rows = []
            for start in (0, 40, 80, 120):
                chunk = fetch_band(lo, hi, 50, start=start)
                rows.extend(chunk)
                if len(chunk) < 50:
                    break
        except Exception as exc:  # noqa: BLE001
            print("  failed:", exc, flush=True)
            continue
        # Prefer popular / well-played
        rows.sort(key=lambda r: (int(r.get("NbPlays") or 0), int(r.get("Popularity") or 0)), reverse=True)
        for row in rows:
            if len(buckets[i]) >= need:
                break
            pid = row["PuzzleId"]
            if pid in seen:
                continue
            item = convert(row)
            if item is None:
                continue
            buckets[i].append(item)
            seen.add(pid)
        print(f"  kept {len(buckets[i])}/{need}", flush=True)

    puzzles = [p for b in buckets for p in b]
    puzzles.sort(key=lambda p: (p["rating"], p["id"]))
    OUT.write_text(json.dumps(puzzles, indent=2), encoding="utf-8")
    print(f"Wrote {len(puzzles)} puzzles to {OUT}", flush=True)
    return 0 if len(puzzles) >= 50 else 1


if __name__ == "__main__":
    sys.exit(main())
