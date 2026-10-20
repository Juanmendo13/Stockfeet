from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RewardResult:
    coins: int
    xp: int
    message: str


def puzzle_reward(
    *,
    rating: int,
    perfect: bool,
    first_try: bool,
    streak_after: int,
    seconds: float,
) -> RewardResult:
    """Better solves → more FeetCoins. Streak and speed multiply rewards."""
    base = 8 + max(0, (rating - 600) // 80)
    coins = base
    xp = 10 + rating // 100

    if first_try:
        coins += 6
        xp += 4
    if perfect:
        coins += 10
        xp += 6
    if seconds <= 15:
        coins += 8
        xp += 3
    elif seconds <= 45:
        coins += 4

    streak_bonus = min(25, streak_after * 2)
    coins += streak_bonus
    xp += streak_after

    parts = [f"+{coins} FeetCoins", f"+{xp} XP"]
    if first_try:
        parts.append("first try")
    if perfect:
        parts.append("perfect")
    if streak_after >= 2:
        parts.append(f"streak x{streak_after}")
    if seconds <= 15:
        parts.append("speed bonus")

    return RewardResult(coins=coins, xp=xp, message=" · ".join(parts))


def fail_penalty() -> RewardResult:
    return RewardResult(coins=0, xp=1, message="Puzzle failed — streak reset. +1 XP for trying.")
