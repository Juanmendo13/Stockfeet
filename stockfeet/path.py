from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PathStage:
    id: str
    name: str
    blurb: str
    rating: int
    themes: tuple[str, ...]  # preferred; empty = any
    needed: int  # solves to clear the stage
    icon: str = "♟"


# Beginner → hardest. Themes prefer Lichess tags when present in the DB.
PATH_STAGES: tuple[PathStage, ...] = (
    PathStage(
        "checks",
        "First checks",
        "Spot simple mates and hanging pieces.",
        600,
        ("mateIn1", "hangingPiece", "oneMove"),
        5,
        "①",
    ),
    PathStage(
        "mate1",
        "Mate in one",
        "Finish the game in a single move.",
        750,
        ("mateIn1",),
        5,
        "♚",
    ),
    PathStage(
        "hanging",
        "Free pieces",
        "Take what the opponent left hanging.",
        850,
        ("hangingPiece", "oneMove"),
        5,
        "♟",
    ),
    PathStage(
        "forks",
        "Forks",
        "Attack two things at once.",
        950,
        ("fork",),
        6,
        "♞",
    ),
    PathStage(
        "pins",
        "Pins & skewers",
        "Line tactics that freeze or pierce.",
        1050,
        ("pin", "skewer"),
        6,
        "♝",
    ),
    PathStage(
        "discovered",
        "Discovered attacks",
        "Move one piece, reveal another.",
        1150,
        ("discoveredAttack", "discoveredCheck"),
        6,
        "☢",
    ),
    PathStage(
        "mate2",
        "Mate in two",
        "Short forced mates.",
        1250,
        ("mateIn2",),
        6,
        "➁",
    ),
    PathStage(
        "intermediate",
        "Intermediate tactics",
        "Sacrifices, deflections, distractions.",
        1400,
        ("sacrifice", "deflection", "attraction"),
        7,
        "⚡",
    ),
    PathStage(
        "patterns",
        "Advanced patterns",
        "Clearance, quiet moves, advanced pawns.",
        1550,
        ("clearance", "quietMove", "advancedPawn"),
        7,
        "✦",
    ),
    PathStage(
        "hard",
        "Hard tactics",
        "Longer lines and tougher calculation.",
        1700,
        (),
        8,
        "🔥",
    ),
    PathStage(
        "expert",
        "Expert",
        "Sharp positions around club-expert level.",
        1850,
        (),
        8,
        "★",
    ),
    PathStage(
        "master",
        "Master",
        "Master-strength puzzles.",
        2050,
        (),
        8,
        "♛",
    ),
    PathStage(
        "gm",
        "Grandmaster",
        "Deep, unforgiving calculation.",
        2250,
        (),
        8,
        "👑",
    ),
    PathStage(
        "elite",
        "Elite",
        "Near the top of the curated pack.",
        2450,
        (),
        8,
        "💎",
    ),
    PathStage(
        "legendary",
        "Legendary",
        "The hardest band in Stockfeet.",
        2650,
        (),
        10,
        "🏆",
    ),
)


def stage_count() -> int:
    return len(PATH_STAGES)


def get_stage(index: int) -> PathStage:
    idx = max(0, min(index, len(PATH_STAGES) - 1))
    return PATH_STAGES[idx]


def path_complete(stage_index: int) -> bool:
    return stage_index >= len(PATH_STAGES)


def stage_progress_label(stage_index: int, solved_in_stage: int) -> str:
    if path_complete(stage_index):
        return "Path complete — Legendary cleared"
    stage = get_stage(stage_index)
    return (
        f"Stage {stage_index + 1}/{len(PATH_STAGES)} · {stage.name} "
        f"({solved_in_stage}/{stage.needed})"
    )


def theme_for_stage(stage: PathStage) -> str | None:
    """Pick one preferred theme, or None for any."""
    if not stage.themes:
        return None
    return stage.themes[0]


def apply_path_solve(
    *,
    stage_index: int,
    solved_in_stage: int,
    perfect: bool,
) -> tuple[int, int, bool, int]:
    """
    Advance path after a successful solve.

    Returns (new_stage_index, new_solved_in_stage, stage_cleared, bonus_coins).
    """
    if path_complete(stage_index):
        return stage_index, solved_in_stage, False, 0

    stage = get_stage(stage_index)
    gained = 1
    solved = solved_in_stage + gained
    bonus = 8 + stage_index * 2
    if perfect:
        bonus += 5

    if solved >= stage.needed:
        next_idx = stage_index + 1
        clear_bonus = 40 + stage_index * 15
        return next_idx, 0, True, bonus + clear_bonus
    return stage_index, solved, False, bonus


def skip_to_stage(
    *,
    current_index: int,
    target_index: int,
    skipped_ids: list[str],
) -> tuple[int, int, list[str]]:
    """
    Jump the path cursor to target_index.

    Marks intermediate stages (current..target-1) as skipped when jumping ahead.
    Returns (new_stage_index, new_solved_in_stage, updated_skipped_ids).
    """
    n = len(PATH_STAGES)
    target = max(0, min(target_index, n))  # n == complete
    skipped = list(skipped_ids)
    if target > current_index:
        for i in range(current_index, min(target, n)):
            sid = PATH_STAGES[i].id
            if sid not in skipped:
                skipped.append(sid)
    return target, 0, skipped
