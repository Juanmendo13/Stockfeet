from __future__ import annotations

import json
import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import chess


@dataclass(frozen=True)
class Puzzle:
    id: str
    rating: int
    themes: tuple[str, ...]
    fen: str
    solution: tuple[str, ...]
    title: str
    hint: str

    def board(self) -> chess.Board:
        return chess.Board(self.fen)


def _pack_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "puzzles.json"


def _db_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "puzzles.sqlite"


def has_sqlite_db() -> bool:
    return _db_path().exists()


def puzzle_count() -> int:
    if has_sqlite_db():
        with sqlite3.connect(_db_path()) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM puzzles").fetchone()[0])
    return len(load_puzzles_json())


def _row_to_puzzle(row: sqlite3.Row | tuple) -> Puzzle:
    if isinstance(row, sqlite3.Row):
        data = dict(row)
    else:
        keys = ("id", "rating", "themes", "fen", "solution", "title", "hint")
        data = dict(zip(keys, row[:7], strict=False))
    themes = tuple((data.get("themes") or "").split())
    solution = tuple((data.get("solution") or "").split())
    return Puzzle(
        id=str(data["id"]),
        rating=int(data["rating"]),
        themes=themes,
        fen=str(data["fen"]),
        solution=solution,
        title=str(data.get("title") or data["id"]),
        hint=str(data.get("hint") or ""),
    )


def themes_available_db() -> list[str]:
    if not has_sqlite_db():
        return themes_available(load_puzzles_json())
    found: set[str] = set()
    with sqlite3.connect(_db_path()) as conn:
        for (themes,) in conn.execute("SELECT themes FROM puzzles"):
            found.update((themes or "").split())
    return sorted(found)


def load_puzzles_json(path: Path | None = None) -> list[Puzzle]:
    target = path or _pack_path()
    if not target.exists():
        return []
    raw = json.loads(target.read_text(encoding="utf-8"))
    puzzles: list[Puzzle] = []
    for item in raw:
        puzzles.append(
            Puzzle(
                id=item["id"],
                rating=int(item["rating"]),
                themes=tuple(item.get("themes") or ()),
                fen=item["fen"],
                solution=tuple(item["solution"]),
                title=item.get("title") or item["id"],
                hint=item.get("hint") or "",
            )
        )
    return puzzles


def load_puzzles(path: Path | None = None) -> list[Puzzle]:
    """Compatibility helper: prefer a sample from SQLite, else JSON pack."""
    if path is not None:
        return load_puzzles_json(path)
    if has_sqlite_db():
        with sqlite3.connect(_db_path()) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, rating, themes, fen, solution, title, hint
                FROM puzzles
                ORDER BY rating
                LIMIT 5000
                """
            ).fetchall()
        return [_row_to_puzzle(r) for r in rows]
    return load_puzzles_json()


def themes_available(puzzles: list[Puzzle] | None = None) -> list[str]:
    if has_sqlite_db() and puzzles is None:
        return themes_available_db()
    puzzles = puzzles if puzzles is not None else load_puzzles()
    found: set[str] = set()
    for p in puzzles:
        found.update(p.themes)
    return sorted(found)


def pick_puzzle(
    puzzles: list[Puzzle] | None = None,
    *,
    rating: int,
    theme: str | None = None,
    exclude_ids: set[str] | None = None,
) -> Puzzle | None:
    exclude_ids = exclude_ids or set()
    if has_sqlite_db() and puzzles is None:
        return pick_puzzle_db(rating=rating, theme=theme, exclude_ids=exclude_ids)

    puzzles = puzzles if puzzles is not None else load_puzzles()
    pool = [p for p in puzzles if p.id not in exclude_ids]
    if theme and theme != "all":
        pool = [p for p in pool if theme in p.themes]
    if not pool:
        pool = [p for p in puzzles if theme in p.themes] if theme and theme != "all" else list(puzzles)
    if not pool:
        return None

    for window in (150, 300, 500, 10_000):
        near = [p for p in pool if abs(p.rating - rating) <= window]
        if near:
            near.sort(key=lambda p: abs(p.rating - rating))
            top = near[: min(12, len(near))]
            return random.choice(top)
    return random.choice(pool)


def pick_puzzle_db(
    *,
    rating: int,
    theme: str | None = None,
    exclude_ids: set[str] | None = None,
) -> Puzzle | None:
    exclude_ids = exclude_ids or set()
    theme = theme or "all"
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        for window in (120, 250, 450, 900, 10_000):
            lo, hi = rating - window, rating + window
            params: list[object] = [lo, hi]
            sql = (
                "SELECT id, rating, themes, fen, solution, title, hint "
                "FROM puzzles WHERE rating BETWEEN ? AND ?"
            )
            if theme != "all":
                # Word-boundary-ish match so "pin" does not match "opening".
                sql += " AND (' ' || themes || ' ') LIKE ?"
                params.append(f"% {theme} %")
            sql += " ORDER BY ABS(rating - ?) LIMIT 80"
            params.append(rating)
            rows = [_row_to_puzzle(r) for r in conn.execute(sql, params).fetchall()]
            rows = [p for p in rows if p.id not in exclude_ids]
            if rows:
                # Prefer closest ratings among the candidates.
                rows.sort(key=lambda p: abs(p.rating - rating))
                return random.choice(rows[:16])
    return None


def pick_puzzle_for_path(
    *,
    rating: int,
    themes: tuple[str, ...],
    exclude_ids: set[str] | None = None,
) -> Puzzle | None:
    """Try preferred themes in order, then any puzzle near rating."""
    exclude_ids = exclude_ids or set()
    for theme in themes:
        puzzle = pick_puzzle(rating=rating, theme=theme, exclude_ids=exclude_ids)
        if puzzle is not None:
            return puzzle
    return pick_puzzle(rating=rating, theme="all", exclude_ids=exclude_ids)


class PuzzleSession:
    """Tracks multi-move puzzle progress. Solution includes opponent replies."""

    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle = puzzle
        self.board = puzzle.board()
        self.ply = 0
        self.wrong_attempts = 0
        self.perfect = True
        self.finished = False
        self.success = False

    @property
    def player_to_move(self) -> bool:
        return self.ply % 2 == 0 and not self.finished

    def expected_move(self) -> chess.Move | None:
        if self.ply >= len(self.puzzle.solution):
            return None
        return chess.Move.from_uci(self.puzzle.solution[self.ply])

    def _is_acceptable(self, move: chess.Move, expected: chess.Move) -> bool:
        if move == expected:
            return True
        if (
            move.from_square == expected.from_square
            and move.to_square == expected.to_square
            and move.promotion == expected.promotion
        ):
            return True
        if "mateIn1" in self.puzzle.themes and self.ply == len(self.puzzle.solution) - 1:
            board = self.board.copy()
            if move in board.legal_moves:
                board.push(move)
                if board.is_checkmate():
                    return True
        return False

    def try_move(self, move: chess.Move) -> str:
        if self.finished:
            return "done"
        expected = self.expected_move()
        if expected is None:
            self.finished = True
            self.success = True
            return "solved"
        if not self._is_acceptable(move, expected):
            self.wrong_attempts += 1
            self.perfect = False
            return "wrong"

        self.board.push(move)
        self.ply += 1
        if self.board.is_checkmate() or self.ply >= len(self.puzzle.solution):
            self.finished = True
            self.success = True
            return "solved"

        if self.ply < len(self.puzzle.solution) and self.ply % 2 == 1:
            reply = chess.Move.from_uci(self.puzzle.solution[self.ply])
            if reply in self.board.legal_moves:
                self.board.push(reply)
                self.ply += 1
                if self.ply >= len(self.puzzle.solution) or self.board.is_checkmate():
                    self.finished = True
                    self.success = True
                    return "solved"
            else:
                self.finished = True
                self.success = True
                return "solved"
        return "ok"
