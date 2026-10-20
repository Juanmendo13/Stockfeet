from __future__ import annotations

from dataclasses import dataclass

import chess

from stockfeet.engine import AnalysisLine, PositionAnalysis


@dataclass(frozen=True)
class MoveReview:
    played: chess.Move
    best: chess.Move | None
    classification: str
    loss_cp: int | None
    summary: str
    tip: str


ELO_BANDS = (
    (800, "beginner"),
    (1200, "improving"),
    (1600, "club"),
    (2000, "strong club"),
    (2300, "expert"),
    (2500, "master"),
    (2800, "super-GM territory"),
)


def elo_band(elo: int) -> str:
    label = "beginner"
    for threshold, name in ELO_BANDS:
        if elo >= threshold:
            label = name
    return label


def classify_move(
    *,
    played: chess.Move,
    before: PositionAnalysis,
    after_best_for_opponent: PositionAnalysis | None = None,
) -> MoveReview:
    """Classify a played move using lc0 multipv before the move (White POV scores)."""
    best = before.best
    if best is None:
        return MoveReview(
            played=played,
            best=None,
            classification="unknown",
            loss_cp=None,
            summary="lc0 did not return a principal variation.",
            tip="Give the engine more time (STOCKFEET_MOVETIME_MS) and retry.",
        )

    played_line = next((line for line in before.multipv if line.move == played), None)
    loss: int | None = None
    if best.mate is not None and (played_line is None or played_line.mate != best.mate):
        classification = "blunder" if played != best.move else "best"
        loss = None
    elif played == best.move:
        classification = "best"
        loss = 0
    elif played_line is not None and best.score_cp is not None and played_line.score_cp is not None:
        # Scores are White POV; loss for the side to move.
        stm_white = chess.Board(before.fen).turn == chess.WHITE
        if stm_white:
            loss = best.score_cp - played_line.score_cp
        else:
            loss = played_line.score_cp - best.score_cp
        loss = max(0, loss)
        classification = _class_from_loss(loss)
    else:
        classification = "inaccuracy"
        loss = None

    summary, tip = _messages(classification, played, best, loss)
    return MoveReview(
        played=played,
        best=best.move,
        classification=classification,
        loss_cp=loss,
        summary=summary,
        tip=tip,
    )


def _class_from_loss(loss_cp: int) -> str:
    if loss_cp <= 20:
        return "excellent"
    if loss_cp <= 50:
        return "good"
    if loss_cp <= 100:
        return "inaccuracy"
    if loss_cp <= 300:
        return "mistake"
    return "blunder"


def _messages(
    classification: str,
    played: chess.Move,
    best: AnalysisLine,
    loss: int | None,
) -> tuple[str, str]:
    uci = played.uci()
    best_uci = best.move.uci()
    loss_txt = f" (~{loss} cp)" if loss is not None else ""
    table = {
        "best": (
            f"{uci} matches lc0's top choice ({best.score_text()}).",
            "Ask why this move works: threats, piece activity, and pawn structure.",
        ),
        "excellent": (
            f"{uci} is nearly as strong as {best_uci}{loss_txt}.",
            "Compare both ideas — understanding near-best alternatives builds intuition.",
        ),
        "good": (
            f"{uci} is solid; lc0 prefers {best_uci}{loss_txt}.",
            "Check if you missed a forcing line (checks, captures, threats).",
        ),
        "inaccuracy": (
            f"{uci} drifts from the best plan ({best_uci}){loss_txt}.",
            "Pause on candidate moves: what does the opponent threaten next?",
        ),
        "mistake": (
            f"{uci} is a real error versus {best_uci}{loss_txt}.",
            "Recalculate tactics from the previous ply before moving on.",
        ),
        "blunder": (
            f"{uci} hangs a lot of value; lc0 wanted {best_uci}{loss_txt}.",
            "Before each move, scan: checks, captures, threats (CCT).",
        ),
    }
    return table.get(
        classification,
        (f"Played {uci}; lc0 top line starts with {best_uci}.", "Review the PV slowly."),
    )


def improvement_plan(elo: int) -> list[str]:
    band = elo_band(elo)
    plans: dict[str, list[str]] = {
        "beginner": [
            "Daily: 15–20 puzzles focusing on hanging pieces.",
            "Learn piece values and always ask 'is this square safe?'.",
            "Play longer games (≥15|10); review every blunder with lc0.",
        ],
        "improving": [
            "Tactics: forks, pins, skewers — mixed motifs, not only mates.",
            "One opening for White and a coherent reply as Black; learn ideas, not only moves.",
            "Endgames: K+P vs K, opposition, basic rook endgames.",
        ],
        "club": [
            "Annotate your losses before opening lc0; then compare.",
            "Study typical middlegame plans from your openings.",
            "Solve calculation exercises with a clock (visualize 3–5 ply).",
        ],
        "strong club": [
            "Deep dive into 2–3 pawn structures you actually play.",
            "Practice converting small advantages; fewer draws from winning positions.",
            "Use lc0 multipv to learn candidate-move selection, not only the top move.",
        ],
        "expert": [
            "Critical-position training: choose moves under time pressure, then analyse.",
            "Refine opening repertoire with lc0; keep human-usable plans.",
            "Study classical games in your structures for strategic patterns.",
        ],
        "master": [
            "Targeted endgame technique and practical decision speed.",
            "Use lc0 to stress-test novelties and evaluate imbalances.",
            "Review psychological leaks: time trouble, forcing draws, tilt.",
        ],
        "super-GM territory": [
            "Engine work is about nuance and prep; human judgment still decides.",
            "Match-style reviews: risk management and opponent-specific prep.",
            "Physical/mental routine matters as much as opening files.",
        ],
    }
    return plans.get(band, plans["club"])
