from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import chess
import chess.engine


@dataclass(frozen=True)
class AnalysisLine:
    move: chess.Move
    score_cp: int | None
    mate: int | None
    pv: list[chess.Move]

    def score_text(self) -> str:
        if self.mate is not None:
            return f"M{self.mate}"
        if self.score_cp is None:
            return "?"
        return f"{self.score_cp / 100:+.2f}"


@dataclass(frozen=True)
class PositionAnalysis:
    fen: str
    best: AnalysisLine | None
    multipv: list[AnalysisLine]
    depth: int | None


class Lc0Engine:
    """Thin UCI wrapper around an external lc0 binary (separate process)."""

    def __init__(
        self,
        binary: Path,
        *,
        weights: Path | None = None,
        movetime_ms: int = 1000,
    ) -> None:
        self.binary = binary
        self.weights = weights
        self.movetime_ms = movetime_ms
        self._engine: chess.engine.SimpleEngine | None = None

    def __enter__(self) -> Lc0Engine:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def open(self) -> None:
        if self._engine is not None:
            return
        # Run from lc0's folder so CUDA DLLs + default nets resolve correctly.
        cwd = str(self.binary.parent)
        cmd: list[str] = [str(self.binary)]
        if self.weights is not None:
            # gflags-style: --weights=PATH (space-separated form is unreliable on Windows)
            cmd.append(f"--weights={self.weights}")
        self._engine = chess.engine.SimpleEngine.popen_uci(cmd, cwd=cwd)
        try:
            self._engine.configure({})
        except chess.engine.EngineError:
            pass

    def close(self) -> None:
        if self._engine is not None:
            self._engine.quit()
            self._engine = None

    @property
    def engine(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            raise RuntimeError("Lc0Engine is not open")
        return self._engine

    def id_name(self) -> str:
        return str(self.engine.id.get("name", "lc0"))

    def play(
        self,
        board: chess.Board,
        *,
        movetime_ms: int | None = None,
        target_elo: int | None = None,
    ) -> chess.Move:
        """Play a move. If target_elo is set, mimic that strength (Full ≈ raw lc0)."""
        if target_elo is not None and target_elo < 2750:
            return self.play_like_elo(board, target_elo)

        limit = chess.engine.Limit(time=(movetime_ms or self.movetime_ms) / 1000)
        result = self.engine.play(board, limit)
        if result.move is None:
            raise RuntimeError("lc0 returned no move")
        return result.move

    def play_like_elo(self, board: chess.Board, target_elo: int) -> chess.Move:
        from stockfeet.human_book import pick_book_move
        from stockfeet.strength import pick_human_move, strength_for_elo

        # Prefer real human moves from Lichess when this position is in the book.
        book = pick_book_move(board, target_elo)
        if book is not None:
            return book

        cfg = strength_for_elo(target_elo)
        analysis = self.analyse(
            board,
            movetime_ms=cfg.movetime_ms,
            multipv=cfg.multipv,
        )
        if analysis.best is None:
            limit = chess.engine.Limit(time=cfg.movetime_ms / 1000)
            result = self.engine.play(board, limit)
            if result.move is None:
                raise RuntimeError("lc0 returned no move")
            return result.move
        return pick_human_move(analysis, board, cfg)

    def analyse(
        self,
        board: chess.Board,
        *,
        movetime_ms: int | None = None,
        multipv: int = 3,
    ) -> PositionAnalysis:
        limit = chess.engine.Limit(time=(movetime_ms or self.movetime_ms) / 1000)
        info = self.engine.analyse(board, limit, multipv=max(1, multipv))
        if isinstance(info, dict):
            infos = [info]
        else:
            infos = list(info)

        lines: list[AnalysisLine] = []
        depth: int | None = None
        for item in infos:
            depth = item.get("depth", depth)
            pv = list(item.get("pv") or [])
            if not pv:
                continue
            score = item.get("score")
            cp: int | None = None
            mate: int | None = None
            if score is not None:
                pov = score.white()
                if pov.is_mate():
                    mate = pov.mate()
                else:
                    cp = pov.score()
            lines.append(AnalysisLine(move=pv[0], score_cp=cp, mate=mate, pv=pv))

        return PositionAnalysis(
            fen=board.fen(),
            best=lines[0] if lines else None,
            multipv=lines,
            depth=depth,
        )
