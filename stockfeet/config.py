from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    # Project root .env (next to pyproject.toml)
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    load_dotenv()  # also cwd


@dataclass(frozen=True)
class Settings:
    lc0_path: Path
    lc0_weights: Path | None
    movetime_ms: int
    openai_api_key: str | None
    openai_base_url: str
    openai_model: str

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def lc0_ready(self) -> bool:
        return self.lc0_path.exists()

    def require_lc0(self) -> None:
        if not self.lc0_path:
            raise FileNotFoundError(
                "STOCKFEET_LC0_PATH is not set. Copy .env.example to .env and "
                "point it at your lc0 binary (https://lczero.org/play/download/)."
            )
        if not self.lc0_path.exists():
            raise FileNotFoundError(
                f"lc0 binary not found at {self.lc0_path}.\n"
                "Download from https://lczero.org/play/download/ "
                "(Windows CUDA or CPU build) and update STOCKFEET_LC0_PATH in .env."
            )
        if self.lc0_weights is not None and not self.lc0_weights.exists():
            raise FileNotFoundError(f"Network weights not found at {self.lc0_weights}")

    @classmethod
    def from_env(cls, *, require_engine: bool = False) -> Settings:
        _load_env()
        raw_path = os.getenv("STOCKFEET_LC0_PATH", "").strip()
        path = Path(raw_path).expanduser() if raw_path else Path("")
        if not path.exists():
            # Prefer vendor copy from `stockfeet setup-lc0` / Setup Stockfeet.bat
            from stockfeet.setup_lc0 import find_lc0_exe

            vendor = find_lc0_exe()
            if vendor is not None:
                path = vendor

        weights_raw = os.getenv("STOCKFEET_LC0_WEIGHTS", "").strip()
        weights = Path(weights_raw).expanduser() if weights_raw else None

        movetime = int(os.getenv("STOCKFEET_MOVETIME_MS", "1000"))
        settings = cls(
            lc0_path=path,
            lc0_weights=weights,
            movetime_ms=max(50, movetime),
            openai_api_key=os.getenv("STOCKFEET_OPENAI_API_KEY") or None,
            openai_base_url=os.getenv(
                "STOCKFEET_OPENAI_BASE_URL", "https://api.openai.com/v1"
            ).rstrip("/"),
            openai_model=os.getenv("STOCKFEET_OPENAI_MODEL", "gpt-4o-mini"),
        )
        if require_engine:
            settings.require_lc0()
        return settings
