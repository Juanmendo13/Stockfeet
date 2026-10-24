# Stockfeet

**Powered by [Leela Chess Zero (lc0)](https://lczero.org/)** — coach, puzzles, and opponent UI.  
Stockfeet is **not** Stockfish and does **not** claim lc0’s strength as proprietary.

| Piece | License |
| --- | --- |
| Stockfeet app | MIT |
| lc0 engine | GPL-3.0-or-later (separate UCI process) |

See `NOTICE` and `stockfeet about`.

## Try it (Windows)

1. Get the try zip (`Stockfeet-*-try-windows.zip`) **or** clone this repo.
2. Run **`Setup Stockfeet.bat`**
   - creates `.venv`, installs Stockfeet
   - downloads the **official lc0 Windows CPU** build from LCZero
   - opens the hub
3. Requires **Python 3.11+**.

Or from a clone:

```powershell
cd C:\Proyectos\Stockfeet
.\.venv\Scripts\Activate.ps1   # or: python -m venv .venv && .\.venv\Scripts\Activate.ps1
pip install -e .
stockfeet setup-lc0            # official CPU lc0 → vendor/lc0 + .env
stockfeet play
```

Build a shareable try zip:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\make_try_release.ps1
```

## Features

- Play vs **lc0** with Elo limiter + eval bar + coach
- Puzzle path, FeetCoins, skins
- Clear in-app credit: *Powered by Leela Chess Zero*

## Legal

1. Always attribute **Leela Chess Zero**.
2. If you redistribute `lc0`, include GPL text + corresponding source (or a valid written offer).
3. Prefer official LCZero networks; do not market lc0 strength as a closed Stockfeet engine.

Manual engine builds (GPU/CPU): https://lczero.org/play/download/
