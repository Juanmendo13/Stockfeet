# Stockfeet

Coach, puzzles, and chess opponent powered by **Leela Chess Zero (lc0)**.

## Features

- Play vs **lc0** with eval bar + coach
- **Puzzles** (mates, forks, pins, skewers, endgames…) with **FeetCoins** rewards
- **Shop** for board & piece skins
- Profile with streak, XP, and an improvement plan

## Run

```powershell
cd C:\Proyectos\Stockfeet
.\.venv\Scripts\Activate.ps1
stockfeet play
```

Opens the hub: **Play · Puzzles · Shop · Improve/Profile**.

```powershell
stockfeet play --direct --color white   # single game window
stockfeet play --cli                    # terminal only
```
## Legal stance

1. Attribute **Leela Chess Zero** in the product.
2. If you redistribute `lc0`, include GPL text + corresponding source (or a valid written offer).
3. Only ship network weights with clear redistribution terms (prefer official LCZero nets).
4. Do not market lc0’s strength as a closed proprietary Stockfeet engine.

Stockfeet application code: **MIT**. lc0: **GPL-3.0-or-later**.
