"""Legal / attribution text shown inside Stockfeet."""

from __future__ import annotations

ABOUT_TEXT = """\
Stockfeet v{version}
Chess coach and opponent.

Chess engine: Leela Chess Zero (lc0)
  Website : https://lczero.org/
  Source  : https://github.com/LeelaChessZero/lc0
  License : GPL-3.0-or-later

Stockfeet application code is MIT-licensed.
lc0 and its networks are separate works — see NOTICE in the project root.

Stockfeet is not affiliated with the Leela Chess Zero project or Stockfish.
"""

SHORT_CREDIT = (
    "Analysis by Leela Chess Zero (lc0), GPL-3.0-or-later — https://lczero.org/"
)


def about(*, version: str) -> str:
    return ABOUT_TEXT.format(version=version)
