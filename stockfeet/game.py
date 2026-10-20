from __future__ import annotations

from dataclasses import dataclass, field

import chess
import chess.pgn

from stockfeet.coach import Coach
from stockfeet.coach.rules import classify_move
from stockfeet.engine import Lc0Engine


@dataclass
class GameSession:
    engine: Lc0Engine
    coach: Coach
    board: chess.Board = field(default_factory=chess.Board)
    human_color: chess.Color = chess.WHITE
    coach_after_each_move: bool = True
    reviews: list[str] = field(default_factory=list)

    @property
    def human_to_move(self) -> bool:
        return self.board.turn == self.human_color

    def push_human(self, move: chess.Move) -> str | None:
        if move not in self.board.legal_moves:
            raise ValueError(f"Illegal move: {move.uci()}")
        commentary = None
        if self.coach_after_each_move:
            before = self.engine.analyse(self.board, multipv=3)
            review = classify_move(played=move, before=before)
            commentary = self.coach.explain_move(review, before)
            self.reviews.append(commentary)
        self.board.push(move)
        return commentary

    def engine_move(self) -> tuple[chess.Move, str | None]:
        commentary = None
        if self.coach_after_each_move:
            before = self.engine.analyse(self.board, multipv=3)
            move = before.best.move if before.best else self.engine.play(self.board)
            review = classify_move(played=move, before=before)
            commentary = self.coach.explain_move(review, before)
            self.reviews.append(commentary)
        else:
            move = self.engine.play(self.board)
        self.board.push(move)
        return move, commentary

    def to_pgn(self) -> str:
        game = chess.pgn.Game.from_board(self.board)
        game.headers["Event"] = "Stockfeet game"
        game.headers["Site"] = "Stockfeet"
        game.headers["White"] = "Human" if self.human_color == chess.WHITE else "lc0"
        game.headers["Black"] = "lc0" if self.human_color == chess.WHITE else "Human"
        game.headers["Annotator"] = "Stockfeet + Leela Chess Zero (lc0)"
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        return game.accept(exporter)
