"""Legal / attribution text shown inside Stockfeet."""

from __future__ import annotations

ABOUT_TEXT = """\
Stockfeet v{version}
Chess coach, puzzles, and opponent.

══════════════════════════════════════
POWERED BY LEELA CHESS ZERO (lc0)
══════════════════════════════════════
  Stockfeet is not an original chess engine.
  All play / analysis strength comes from lc0.

  Website : https://lczero.org/
  Source  : https://github.com/LeelaChessZero/lc0
  License : GPL-3.0-or-later

  Download lc0: https://lczero.org/play/download/
  Or run:  stockfeet setup-lc0

Stockfeet application code is MIT-licensed.
lc0 and its networks are separate works — see NOTICE.

Stockfeet is not affiliated with the Leela Chess Zero project or Stockfish.
"""

SHORT_CREDIT = (
    "Powered by Leela Chess Zero (lc0) · GPL-3.0-or-later · https://lczero.org/"
)


def about(*, version: str) -> str:
    return ABOUT_TEXT.format(version=version)
