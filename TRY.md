# Try Stockfeet (Windows)

**Stockfeet is powered by [Leela Chess Zero (lc0)](https://lczero.org/)** — not Stockfish.  
App code: **MIT**. Engine: **GPL-3.0-or-later** (separate UCI process). See `NOTICE`.

## Quick try

1. Unzip this folder.
2. Double-click **`Setup Stockfeet.bat`**
   - installs Stockfeet into a local `.venv`
   - downloads the **official lc0 Windows CPU** build from LCZero (~23 MB)
   - writes `.env` and opens the hub
3. Need Python **3.11+** on PATH ([python.org](https://www.python.org/downloads/)).

## What you get

- Play vs **lc0** (Elo-limited opponent)
- Puzzle path, shop skins, coach
- Clear credit: analysis by Leela Chess Zero

## Manual lc0

If the automatic download fails:

1. Get a build from https://lczero.org/play/download/
2. Set `STOCKFEET_LC0_PATH` in `.env` to your `lc0.exe`
3. Run `Abrir Stockfeet.bat`

GPU users can swap the CPU build for a CUDA/ONNX package from the same page.

## Legal

Redistributing `lc0.exe` means you must also offer GPL text + corresponding source (or a valid written offer). Stockfeet’s try zip **does not** ship `lc0.exe`; the setup script downloads it from the official LCZero release.
