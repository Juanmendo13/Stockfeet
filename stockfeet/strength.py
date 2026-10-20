from __future__ import annotations

import math
import random
from dataclasses import dataclass

import chess

from stockfeet.engine import AnalysisLine, PositionAnalysis


@dataclass(frozen=True)
class StrengthConfig:
    """How Stockfeet should play when mimicking a human Elo."""

    elo: int
    movetime_ms: int
    multipv: int
    softmax_temp_cp: float
    blunder_chance: float
    noise_sigma_cp: float
    max_loss_cp: float
    target_best_rate: float


def clamp_elo(elo: int) -> int:
    return max(600, min(2800, int(elo)))


def _unit(elo: int) -> float:
    """0 at 600 Elo → 1 at 2800."""
    return (clamp_elo(elo) - 600) / (2800 - 600)


def target_best_move_rate(elo: int) -> float:
    """Share of engine-best moves a human at this Elo roughly plays.

    Important: ~800 Elo is a beginner, not random. They still take free pieces
    and develop often; they miss tactics and miscalculate, they do not hang
    queens every other move.
    """
    t = _unit(elo)
    # ~0.50 @600, ~0.55 @800, ~0.64 @1200, ~0.74 @1600, ~0.84 @2000, ~0.93 @2400, ~0.98 @2800
    return 0.50 + 0.48 * (t**0.90)


def strength_for_elo(elo: int) -> StrengthConfig:
    """Map target Elo to search/time and move-selection softness.

    Curves are intentionally gentle at the low end so club beginners stay
    coherent, while mid/high Elo still separates clearly.
    """
    elo = clamp_elo(elo)
    t = _unit(elo)

    # Give beginners enough MultiPV quality time (too little → nonsense moves).
    movetime = int(160 + (t**1.25) * 1450)

    multipv = int(round(7 - 4.5 * t))
    multipv = max(2, min(7, multipv))

    # Mild softmax temperature — prefer near-best, allow second/third choices.
    temp = 14.0 + 90.0 * ((1.0 - t) ** 1.35)

    # Rare deliberate worse picks (not every few moves).
    blunder = 0.055 * ((1.0 - t) ** 1.7)

    # Light score noise (old ~150cp at 800 made the bot look braindead).
    noise = 4.0 + 42.0 * ((1.0 - t) ** 1.4)

    # Cap how bad a sampled alternative can be vs best.
    # ~115cp @800, ~80 @1200, ~50 @1800, ~20 @2800
    max_loss = 22.0 + 105.0 * ((1.0 - t) ** 1.25)

    return StrengthConfig(
        elo=elo,
        movetime_ms=movetime,
        multipv=multipv,
        softmax_temp_cp=temp,
        blunder_chance=blunder,
        noise_sigma_cp=noise,
        max_loss_cp=max_loss,
        target_best_rate=target_best_move_rate(elo),
    )


def _stm_score(line: AnalysisLine, turn: chess.Color) -> float:
    """Score from the side-to-move point of view (higher = better for stm)."""
    if line.mate is not None:
        mate = line.mate if turn == chess.WHITE else -line.mate
        return 50_000.0 - abs(mate) if mate > 0 else -50_000.0 + abs(mate)
    cp = float(line.score_cp if line.score_cp is not None else 0)
    return cp if turn == chess.WHITE else -cp


def _calibrate_temp(scores: list[float], target_best: float, base_temp: float) -> float:
    """Nudge temperature so softmax P(best) is close to the Elo target rate."""
    if len(scores) < 2:
        return base_temp
    best = max(scores)
    target = min(0.98, max(0.40, target_best))
    temp = max(10.0, base_temp)
    for _ in range(8):
        weights = [math.exp((s - best) / temp) for s in scores]
        total = sum(weights) or 1.0
        p_best = max(weights) / total
        if abs(p_best - target) < 0.035:
            break
        if p_best > target:
            temp *= 1.18
        else:
            temp /= 1.15
        temp = max(10.0, min(220.0, temp))
    return temp


def pick_human_move(
    analysis: PositionAnalysis,
    board: chess.Board,
    config: StrengthConfig,
    *,
    rng: random.Random | None = None,
) -> chess.Move:
    """Choose a move that a ~config.elo player might play from MultiPV lines."""
    rng = rng or random.Random()
    lines = [ln for ln in analysis.multipv if ln.move in board.legal_moves]
    if not lines:
        return rng.choice(list(board.legal_moves))

    scores = [_stm_score(ln, board.turn) for ln in lines]
    best = max(scores)

    # Even beginners usually avoid forced mate-in-1/2 if another MultiPV line exists.
    if config.elo >= 700:
        non_mated = [i for i, s in enumerate(scores) if s > -40_000]
        if non_mated and len(non_mated) < len(scores):
            lines = [lines[i] for i in non_mated]
            scores = [scores[i] for i in non_mated]
            best = max(scores)

    # Keep only near-best alternatives (plus always best + second-best).
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    keep: list[int] = []
    for i, s in enumerate(scores):
        if i == order[0] or (best - s) <= config.max_loss_cp:
            keep.append(i)
    if len(order) >= 2 and order[1] not in keep:
        keep.append(order[1])
    keep = list(dict.fromkeys(keep))
    lines = [lines[i] for i in keep]
    scores = [scores[i] for i in keep]
    best = max(scores)
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    # Rare mild mistake: pick second/third, not random MultiPV trash.
    if config.blunder_chance > 0 and len(lines) >= 2 and rng.random() < config.blunder_chance:
        # Prefer the runner-up; sometimes third if available.
        pick_i = order[1]
        if len(order) >= 3 and rng.random() < 0.35:
            pick_i = order[2]
        return lines[pick_i].move

    # Noise + Elo-calibrated softmax among the shortlist.
    noisy = [s + rng.gauss(0.0, config.noise_sigma_cp) for s in scores]
    best_noisy = max(noisy)
    temp = _calibrate_temp(noisy, config.target_best_rate, config.softmax_temp_cp)
    weights = [math.exp((s - best_noisy) / temp) for s in noisy]
    total = sum(weights) or 1.0
    r = rng.random() * total
    acc = 0.0
    for line, w in zip(lines, weights, strict=True):
        acc += w
        if r <= acc:
            return line.move
    return lines[order[0]].move
