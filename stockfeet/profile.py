from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


def profile_path() -> Path:
    return Path.home() / ".stockfeet" / "profile.json"


@dataclass
class Profile:
    coins: int = 150
    xp: int = 0
    puzzle_rating: int = 1200
    streak: int = 0
    best_streak: int = 0
    puzzles_solved: int = 0
    puzzles_failed: int = 0
    owned_board_skins: list[str] = field(default_factory=lambda: ["classic"])
    owned_piece_skins: list[str] = field(default_factory=lambda: ["classic"])
    equipped_board: str = "classic"
    equipped_pieces: str = "classic"
    solved_puzzle_ids: list[str] = field(default_factory=list)
    # Progressive puzzle path (beginner → hardest)
    path_stage: int = 0
    path_stage_solved: int = 0
    path_mode: bool = True
    path_skipped: list[str] = field(default_factory=list)

    def save(self, path: Path | None = None) -> None:
        target = path or profile_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | None = None) -> Profile:
        target = path or profile_path()
        if not target.exists():
            profile = cls()
            profile.save(target)
            return profile
        raw = json.loads(target.read_text(encoding="utf-8"))
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        data = {k: v for k, v in raw.items() if k in known}
        profile = cls(**data)
        # Ensure defaults always owned/equipped.
        if "classic" not in profile.owned_board_skins:
            profile.owned_board_skins.append("classic")
        if "classic" not in profile.owned_piece_skins:
            profile.owned_piece_skins.append("classic")
        return profile

    def owns_board(self, skin_id: str) -> bool:
        return skin_id in self.owned_board_skins

    def owns_pieces(self, skin_id: str) -> bool:
        return skin_id in self.owned_piece_skins
