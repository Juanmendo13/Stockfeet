from __future__ import annotations

import sys

import chess

UNICODE = {
    "P": "♙",
    "N": "♘",
    "B": "♗",
    "R": "♖",
    "Q": "♕",
    "K": "♔",
    "p": "♟",
    "n": "♞",
    "b": "♝",
    "r": "♜",
    "q": "♛",
    "k": "♚",
}


def _supports_unicode() -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or ""
    return encoding.lower().startswith("utf")


def render_board(board: chess.Board, *, perspective_white: bool = True) -> str:
    use_unicode = _supports_unicode()
    rows: list[str] = []
    ranks = range(7, -1, -1) if perspective_white else range(0, 8)
    files = range(0, 8) if perspective_white else range(7, -1, -1)
    file_labels = "abcdefgh" if perspective_white else "hgfedcba"

    for r in ranks:
        cells: list[str] = []
        for f in files:
            piece = board.piece_at(chess.square(f, r))
            if piece is None:
                cells.append(".")
            elif use_unicode:
                cells.append(UNICODE[piece.symbol()])
            else:
                cells.append(piece.symbol())
        rows.append(f"{r + 1}  " + " ".join(cells))
    rows.append("   " + " ".join(file_labels))
    return "\n".join(rows)
