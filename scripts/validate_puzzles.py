import json
from pathlib import Path

import chess

raw = json.loads(Path("stockfeet/data/puzzles.json").read_text(encoding="utf-8"))
for p in raw:
    board = chess.Board(p["fen"])
    ok = True
    b = board.copy()
    for i, u in enumerate(p["solution"]):
        if not u:
            print(p["id"], "EMPTY", i)
            ok = False
            break
        try:
            m = chess.Move.from_uci(u)
        except ValueError:
            print(p["id"], "BAD UCI", u)
            ok = False
            break
        if m not in b.legal_moves:
            print(p["id"], "ILLEGAL", u, "fen", b.fen())
            ok = False
            break
        b.push(m)
    if ok:
        print(p["id"], "OK")
