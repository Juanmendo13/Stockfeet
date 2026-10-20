from __future__ import annotations

import math

import chess


def white_advantage_fraction(*, score_cp: int | None, mate: int | None) -> float:
    """Map White-POV score to 0..1 (0 = Black winning, 1 = White winning)."""
    if mate is not None:
        if mate > 0:
            return 0.99
        if mate < 0:
            return 0.01
        return 0.5
    if score_cp is None:
        return 0.5
    # Smooth curve similar to common chess UIs (~pawn scale).
    return 1.0 / (1.0 + math.exp(-score_cp / 290.0))


def format_eval(*, score_cp: int | None, mate: int | None) -> str:
    if mate is not None:
        sign = "+" if mate > 0 else ""
        return f"M{sign}{mate}"
    if score_cp is None:
        return "—"
    return f"{score_cp / 100:+.2f}"


def bottom_fill_fraction(
    white_frac: float,
    *,
    perspective_white: bool,
) -> float:
    """Fraction of the bar filled from the bottom (side closest to the player view)."""
    return white_frac if perspective_white else (1.0 - white_frac)


def score_from_board_result(board: chess.Board) -> tuple[int | None, int | None]:
    if not board.is_game_over():
        return None, None
    if board.is_checkmate():
        # Side to move is mated.
        return (None, -1) if board.turn == chess.WHITE else (None, 1)
    return 0, None
