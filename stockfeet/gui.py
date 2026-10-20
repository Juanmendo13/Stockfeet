from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext

import chess

from stockfeet import __version__
from stockfeet.coach import Coach
from stockfeet.config import Settings
from stockfeet.engine import Lc0Engine
from stockfeet.eval_bar import (
    bottom_fill_fraction,
    format_eval,
    score_from_board_result,
    white_advantage_fraction,
)
from stockfeet.game import GameSession
from stockfeet.legal import SHORT_CREDIT
from stockfeet.profile import Profile

LIGHT = "#f0d9b5"
DARK = "#b58863"
HIGHLIGHT_FROM = "#cac34d"
HIGHLIGHT_TO = "#e6e03a"
SELECT = "#6fa8dc"
LEGAL = "#82c46c"
BOARD_SIZE = 640
SQ = BOARD_SIZE // 8
EVAL_BAR_WIDTH = 28

PIECE_GLYPH = {
    "P": "♙",
    "N": "♘",
    "B": "♗",
    "R": "♖",
    "Q": "♕",
    "K": "♔",
    "p": "♟",
    "n": "♞",
    "b": "♝",
    "r": "♜",
    "q": "♛",
    "k": "♚",
}


class EvalBar(tk.Frame):
    """Vertical evaluation bar (lc0, White POV), oriented with the board."""

    def __init__(self, master: tk.Misc, *, perspective_white: bool) -> None:
        super().__init__(master, background="#1e1e1e")
        self.perspective_white = perspective_white
        self._white_frac = 0.5
        self._label = "0.00"
        self.canvas = tk.Canvas(
            self,
            width=EVAL_BAR_WIDTH,
            height=BOARD_SIZE,
            highlightthickness=0,
            background="#111",
        )
        self.canvas.pack()
        self.score_var = tk.StringVar(value="0.00")
        tk.Label(
            self,
            textvariable=self.score_var,
            font=("Segoe UI", 10, "bold"),
            fg="#f5f5f5",
            bg="#1e1e1e",
            width=6,
        ).pack(pady=(6, 0))
        tk.Label(
            self,
            text="eval",
            font=("Segoe UI", 8),
            fg="#888888",
            bg="#1e1e1e",
        ).pack()
        self.redraw()

    def set_score(self, *, score_cp: int | None, mate: int | None) -> None:
        self._white_frac = white_advantage_fraction(score_cp=score_cp, mate=mate)
        self._label = format_eval(score_cp=score_cp, mate=mate)
        self.score_var.set(self._label)
        self.redraw()

    def set_loading(self) -> None:
        self.score_var.set("…")

    def redraw(self) -> None:
        c = self.canvas
        c.delete("all")
        h = BOARD_SIZE
        w = EVAL_BAR_WIDTH
        fill = bottom_fill_fraction(self._white_frac, perspective_white=self.perspective_white)
        fill = min(1.0, max(0.0, fill))
        bottom_h = int(h * fill)

        if self.perspective_white:
            top_color, bottom_color = "#1a1a1a", "#f5f5f5"
        else:
            top_color, bottom_color = "#f5f5f5", "#1a1a1a"

        c.create_rectangle(0, 0, w, h - bottom_h, fill=top_color, outline="")
        c.create_rectangle(0, h - bottom_h, w, h, fill=bottom_color, outline="")
        c.create_line(0, h // 2, w, h // 2, fill="#666666")


class BoardCanvas(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        *,
        perspective_white: bool,
        on_square=None,
        light: str = LIGHT,
        dark: str = DARK,
        piece_white: str = "#111111",
        piece_black: str = "#0a0a0a",
        board_size: int = BOARD_SIZE,
        interactive: bool = True,
    ) -> None:
        size = max(120, int(board_size))
        super().__init__(
            master,
            width=size,
            height=size,
            highlightthickness=0,
            background="#222",
        )
        self.board_size = size
        self.sq = size // 8
        self.perspective_white = perspective_white
        self.on_square = on_square
        self.light = light
        self.dark = dark
        self.piece_white = piece_white
        self.piece_black = piece_black
        self._selected: chess.Square | None = None
        self._legal_targets: set[chess.Square] = set()
        self._last_move: chess.Move | None = None
        if interactive and on_square is not None:
            self.bind("<Button-1>", self._click)

    def set_selection(
        self,
        selected: chess.Square | None,
        legal_targets: set[chess.Square] | None = None,
    ) -> None:
        self._selected = selected
        self._legal_targets = legal_targets or set()

    def set_last_move(self, move: chess.Move | None) -> None:
        self._last_move = move

    def apply_skin(self, *, light: str, dark: str, piece_white: str, piece_black: str) -> None:
        self.light = light
        self.dark = dark
        self.piece_white = piece_white
        self.piece_black = piece_black

    def draw(self, board: chess.Board) -> None:
        self.delete("all")
        sq = self.sq
        font_size = max(14, int(sq * 0.55))
        coord_size = max(7, int(sq * 0.16))
        for rank in range(8):
            for file in range(8):
                x0, y0 = file * sq, rank * sq
                square = self._view_to_square(file, rank)
                color = self.light if (file + rank) % 2 == 0 else self.dark
                if self._last_move is not None:
                    if square == self._last_move.from_square:
                        color = HIGHLIGHT_FROM
                    elif square == self._last_move.to_square:
                        color = HIGHLIGHT_TO
                if square == self._selected:
                    color = SELECT
                self.create_rectangle(x0, y0, x0 + sq, y0 + sq, fill=color, outline="")
                if square in self._legal_targets:
                    cx, cy = x0 + sq // 2, y0 + sq // 2
                    r = max(4, sq // 8)
                    self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=LEGAL, outline="")

                piece = board.piece_at(square)
                if piece:
                    self.create_text(
                        x0 + sq // 2,
                        y0 + sq // 2,
                        text=PIECE_GLYPH[piece.symbol()],
                        font=("Segoe UI Symbol", font_size),
                        fill=self.piece_white if piece.color == chess.WHITE else self.piece_black,
                    )

                # Coordinates
                if file == 0:
                    label = str(chess.square_rank(square) + 1)
                    self.create_text(
                        x0 + max(6, sq // 8),
                        y0 + max(8, sq // 7),
                        text=label,
                        font=("Segoe UI", coord_size, "bold"),
                        fill="#333",
                    )
                if rank == 7:
                    label = chess.FILE_NAMES[chess.square_file(square)]
                    self.create_text(
                        x0 + sq - max(6, sq // 8),
                        y0 + sq - max(8, sq // 7),
                        text=label,
                        font=("Segoe UI", coord_size, "bold"),
                        fill="#333",
                    )

    def _view_to_square(self, file: int, rank: int) -> chess.Square:
        if self.perspective_white:
            return chess.square(file, 7 - rank)
        return chess.square(7 - file, rank)

    def _click(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if self.on_square is None:
            return
        file = min(7, max(0, event.x // self.sq))
        rank = min(7, max(0, event.y // self.sq))
        self.on_square(self._view_to_square(file, rank))


class StockfeetApp:
    def __init__(
        self,
        settings: Settings,
        *,
        human_color: chess.Color,
        elo: int,
        coach_enabled: bool,
        movetime_ms: int,
        master: tk.Misc | None = None,
        profile: Profile | None = None,
        opponent_elo: int = 1500,
        autoplay: bool = False,
    ) -> None:
        from stockfeet.shop import board_colors, piece_colors

        self.settings = settings
        self.human_color = human_color
        self.elo = elo
        self.opponent_elo = max(600, min(2800, int(opponent_elo)))
        self.coach_enabled = coach_enabled and not autoplay
        self.movetime_ms = movetime_ms
        self.autoplay = autoplay
        self.profile = profile or Profile.load()
        self._owns_root = master is None

        self.root = master if master is not None else tk.Tk()
        if self._owns_root:
            self.root.title(f"Stockfeet {__version__}")
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        else:
            assert isinstance(self.root, (tk.Tk, tk.Toplevel))
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.status = tk.StringVar(value="Starting lc0…")
        self.last_move_var = tk.StringVar(value="Last move: —")
        self.busy = False
        self.selected: chess.Square | None = None
        self._events: queue.Queue[tuple] = queue.Queue()
        self._engine_lock = threading.Lock()
        self._eval_token = 0

        self.engine: Lc0Engine | None = None
        self.session: GameSession | None = None

        bc = board_colors(self.profile.equipped_board)
        pc = piece_colors(self.profile.equipped_pieces)
        self._board_light, self._board_dark = bc
        self._piece_white, self._piece_black = pc

        self._build_ui()
        self.root.after(100, self._boot_engine)
        self.root.after(100, self._poll_events)

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, padx=12, pady=12, background="#1e1e1e")
        outer.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(outer, background="#1e1e1e")
        left.pack(side=tk.LEFT, fill=tk.BOTH)

        color_name = "White" if self.human_color == chess.WHITE else "Black"
        title = (
            f"Stockfeet  ·  AI demo ~{self.opponent_elo} Elo (both sides)"
            if self.autoplay
            else f"Stockfeet  ·  you are {color_name}  ·  opponent ~{self.opponent_elo} Elo"
        )
        tk.Label(
            left,
            text=title,
            font=("Segoe UI", 14, "bold"),
            fg="#f5f5f5",
            bg="#1e1e1e",
        ).pack(anchor="w")
        tk.Label(
            left,
            text=SHORT_CREDIT,
            font=("Segoe UI", 8),
            fg="#aaaaaa",
            bg="#1e1e1e",
            wraplength=BOARD_SIZE,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        board_row = tk.Frame(left, background="#1e1e1e")
        board_row.pack()

        self.eval_bar = EvalBar(board_row, perspective_white=self.human_color == chess.WHITE)
        self.eval_bar.pack(side=tk.LEFT, padx=(0, 10), anchor="n")

        self.board_view = BoardCanvas(
            board_row,
            perspective_white=self.human_color == chess.WHITE,
            on_square=self._on_square,
            light=self._board_light,
            dark=self._board_dark,
            piece_white=self._piece_white,
            piece_black=self._piece_black,
        )
        self.board_view.pack(side=tk.LEFT)

        tk.Label(left, textvariable=self.last_move_var, font=("Segoe UI", 12, "bold"), fg="#ffe082", bg="#1e1e1e").pack(
            anchor="w", pady=(8, 0)
        )
        tk.Label(left, textvariable=self.status, font=("Segoe UI", 11), fg="#dddddd", bg="#1e1e1e").pack(
            anchor="w", pady=(4, 8)
        )

        btns = tk.Frame(left, background="#1e1e1e")
        btns.pack(anchor="w")
        tk.Button(btns, text="Hint", command=self._hint).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btns, text="Resign", command=self._resign).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btns, text="Copy PGN", command=self._copy_pgn).pack(side=tk.LEFT)

        right = tk.Frame(outer, background="#1e1e1e")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))
        tk.Label(right, text="Coach", font=("Segoe UI", 12, "bold"), fg="#f5f5f5", bg="#1e1e1e").pack(anchor="w")
        self.coach_box = scrolledtext.ScrolledText(
            right,
            width=42,
            height=32,
            font=("Consolas", 10),
            bg="#2b2b2b",
            fg="#eaeaea",
            insertbackground="#eaeaea",
            wrap=tk.WORD,
        )
        self.coach_box.pack(fill=tk.BOTH, expand=True)
        self.coach_box.insert(tk.END, "Waiting for moves…\n")
        self.coach_box.configure(state=tk.DISABLED)

    def run(self) -> None:
        if self._owns_root:
            self.root.mainloop()

    def _boot_engine(self) -> None:
        def worker() -> None:
            try:
                eng = Lc0Engine(
                    self.settings.lc0_path,
                    weights=self.settings.lc0_weights,
                    movetime_ms=self.movetime_ms,
                )
                eng.open()
                coach = Coach(self.settings, student_elo=self.elo)
                session = GameSession(
                    engine=eng,
                    coach=coach,
                    human_color=self.human_color,
                    coach_after_each_move=False,  # coach runs after board update
                )
                self._events.put(("ready", eng, session))
            except Exception as exc:  # noqa: BLE001
                self._events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_events(self) -> None:
        try:
            while True:
                event = self._events.get_nowait()
                kind = event[0]
                if kind == "ready":
                    _, eng, session = event
                    self.engine = eng
                    self.session = session
                    self._redraw()
                    self._append_coach(
                        f"Engine online: {eng.id_name()}\n"
                        + (
                            f"Demo mode: both sides play at ~{self.opponent_elo} Elo.\n"
                            if self.autoplay
                            else f"Opponent strength target: ~{self.opponent_elo} Elo "
                            f"(human-limited lc0, not full strength).\n"
                        )
                    )
                    self._schedule_eval()
                    self._continue_turn()
                elif kind == "error":
                    messagebox.showerror("Stockfeet", event[1])
                    self.status.set("Engine failed to start.")
                elif kind == "eval":
                    token, score_cp, mate = event[1], event[2], event[3]
                    if token == self._eval_token:
                        self.eval_bar.set_score(score_cp=score_cp, mate=mate)
                elif kind == "engine_move_ready":
                    move = event[1]
                    assert self.session is not None
                    board = self.session.board
                    san = board.san(move)
                    before = board.copy()
                    board.push(move)
                    self.busy = False
                    self.board_view.set_last_move(move)
                    self.board_view.set_selection(None)
                    self._redraw()
                    self._schedule_eval()
                    side = "White" if before.turn == chess.WHITE else "Black"
                    self.last_move_var.set(f"Last move: {san}  ({move.uci()})  — lc0 ({side})")
                    if board.is_game_over():
                        self._events.put(("game_over", self._result_text()))
                    elif self.autoplay:
                        self.status.set(f"Demo ~{self.opponent_elo} Elo — next move…")
                        self.root.after(350, self._continue_turn)
                    else:
                        self.status.set("Your turn — click a piece, then a destination.")
                    if self.coach_enabled:
                        threading.Thread(
                            target=self._coach_after_engine,
                            args=(before, move),
                            daemon=True,
                        ).start()
                elif kind == "coach_text":
                    self._append_coach(event[1])
                elif kind == "human_move_ready":
                    move, commentary = event[1], event[2]
                    assert self.session is not None
                    board = self.session.board
                    san = board.san(move)
                    board.push(move)
                    self.busy = False
                    self.selected = None
                    self.board_view.set_last_move(move)
                    self.board_view.set_selection(None)
                    self._redraw()
                    self._schedule_eval()
                    self.last_move_var.set(f"Last move: {san}  ({move.uci()})  — you")
                    if commentary:
                        self._append_coach(commentary + "\n")
                    self._continue_turn()
                elif kind == "hint":
                    self.busy = False
                    self.status.set("Your turn.")
                    self._append_coach(event[1] + "\n")
                    # Hint analysis already ran; refresh bar from current position.
                    self._schedule_eval()
                elif kind == "game_over":
                    self.busy = False
                    self._redraw()
                    self._schedule_eval()
                    self.status.set(event[1])
                    self._append_coach(event[1] + "\n")
                    if self.session:
                        self._append_coach(self.session.coach.lesson_for_elo() + "\n")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _continue_turn(self) -> None:
        assert self.session is not None
        if self.session.board.is_game_over():
            self._events.put(("game_over", self._result_text()))
            return
        if not self.autoplay and self.session.human_to_move:
            self.busy = False
            self.status.set("Your turn — click a piece, then a destination.")
            return
        self.busy = True
        self.selected = None
        self.board_view.set_selection(None)
        self._redraw()
        self.status.set(
            f"lc0 (~{self.opponent_elo}) thinking…"
            if self.autoplay
            else "lc0 thinking… watch the board for its move."
        )
        threading.Thread(target=self._engine_turn_worker, daemon=True).start()

    def _engine_turn_worker(self) -> None:
        assert self.session is not None and self.engine is not None
        with self._engine_lock:
            move = self.engine.play(self.session.board, target_elo=self.opponent_elo)
        self._events.put(("engine_move_ready", move))

    def _coach_after_engine(self, before: chess.Board, move: chess.Move) -> None:
        assert self.session is not None and self.engine is not None
        from stockfeet.coach.rules import classify_move

        with self._engine_lock:
            analysis = self.engine.analyse(before, multipv=3)
        review = classify_move(played=move, before=analysis)
        text = self.session.coach.explain_move(review, analysis)
        self._events.put(("coach_text", f"— lc0 move —\n{text}\n"))

    def _schedule_eval(self) -> None:
        if self.session is None or self.engine is None:
            return
        board = self.session.board
        if board.is_game_over():
            cp, mate = score_from_board_result(board)
            self.eval_bar.set_score(score_cp=cp, mate=mate)
            return
        self._eval_token += 1
        token = self._eval_token
        fen = board.fen()
        self.eval_bar.set_loading()
        threading.Thread(target=self._eval_worker, args=(fen, token), daemon=True).start()

    def _eval_worker(self, fen: str, token: int) -> None:
        assert self.engine is not None
        board = chess.Board(fen)
        try:
            with self._engine_lock:
                # Slightly shorter than move time so the bar stays snappy.
                ms = max(200, min(self.movetime_ms, 800))
                analysis = self.engine.analyse(board, movetime_ms=ms, multipv=1)
        except Exception:  # noqa: BLE001
            return
        if analysis.best is None:
            return
        self._events.put(("eval", token, analysis.best.score_cp, analysis.best.mate))

    def _on_square(self, square: chess.Square) -> None:
        if self.autoplay or self.busy or self.session is None:
            return
        if not self.session.human_to_move or self.session.board.is_game_over():
            return

        board = self.session.board
        if self.selected is None:
            piece = board.piece_at(square)
            if piece is None or piece.color != self.human_color:
                return
            self.selected = square
            targets = {m.to_square for m in board.legal_moves if m.from_square == square}
            self.board_view.set_selection(square, targets)
            self._redraw()
            return

        if square == self.selected:
            self.selected = None
            self.board_view.set_selection(None)
            self._redraw()
            return

        move = self._match_move(self.selected, square)
        if move is None:
            piece = board.piece_at(square)
            if piece is not None and piece.color == self.human_color:
                self.selected = square
                targets = {m.to_square for m in board.legal_moves if m.from_square == square}
                self.board_view.set_selection(square, targets)
                self._redraw()
            return

        self.busy = True
        self.status.set("Checking your move…")
        threading.Thread(target=self._human_move_worker, args=(move,), daemon=True).start()

    def _match_move(self, frm: chess.Square, to: chess.Square) -> chess.Move | None:
        assert self.session is not None
        board = self.session.board
        candidates = [m for m in board.legal_moves if m.from_square == frm and m.to_square == to]
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        # Promotion: default to queen
        for m in candidates:
            if m.promotion == chess.QUEEN:
                return m
        return candidates[0]

    def _human_move_worker(self, move: chess.Move) -> None:
        assert self.session is not None and self.engine is not None
        board = self.session.board
        commentary = None
        if self.coach_enabled:
            with self._engine_lock:
                analysis = self.engine.analyse(board, multipv=3)
            from stockfeet.coach.rules import classify_move

            review = classify_move(played=move, before=analysis)
            commentary = self.session.coach.explain_move(review, analysis)
        self._events.put(("human_move_ready", move, commentary))

    def _hint(self) -> None:
        if self.busy or self.session is None or not self.session.human_to_move:
            return
        self.busy = True
        self.status.set("Asking lc0 for a hint…")

        def worker() -> None:
            assert self.session is not None and self.engine is not None
            with self._engine_lock:
                analysis = self.engine.analyse(self.session.board, multipv=3)
            if analysis.best:
                msg = (
                    f"Hint: {analysis.best.move.uci()} "
                    f"[{format_eval(score_cp=analysis.best.score_cp, mate=analysis.best.mate)}]"
                )
            else:
                msg = "No hint available."
            self._events.put(("hint", msg))

        threading.Thread(target=worker, daemon=True).start()

    def _resign(self) -> None:
        if self.session is None:
            return
        self.status.set("You resigned.")
        self._append_coach("You resigned.\n" + self.session.to_pgn() + "\n")
        self.busy = True

    def _copy_pgn(self) -> None:
        if self.session is None:
            return
        pgn = self.session.to_pgn()
        self.root.clipboard_clear()
        self.root.clipboard_append(pgn)
        self.status.set("PGN copied to clipboard.")

    def _redraw(self) -> None:
        if self.session is None:
            return
        self.board_view.draw(self.session.board)

    def _append_coach(self, text: str) -> None:
        self.coach_box.configure(state=tk.NORMAL)
        self.coach_box.insert(tk.END, text + ("" if text.endswith("\n") else "\n"))
        self.coach_box.see(tk.END)
        self.coach_box.configure(state=tk.DISABLED)

    def _result_text(self) -> str:
        assert self.session is not None
        board = self.session.board
        if not board.is_game_over():
            return "Game stopped."
        return f"Result: {board.result(claim_draw=True)}"

    def _on_close(self) -> None:
        if self.engine is not None:
            try:
                self.engine.close()
            except Exception:  # noqa: BLE001
                pass
        self.root.destroy()


def run_gui(
    settings: Settings,
    *,
    human_color: chess.Color | None = None,
    elo: int = 1200,
    opponent_elo: int = 1500,
    coach_enabled: bool = True,
    movetime_ms: int | None = None,
    hub: bool = True,
) -> int:
    if hub:
        from stockfeet.hub import run_hub

        return run_hub(settings)
    app = StockfeetApp(
        settings,
        human_color=human_color if human_color is not None else chess.WHITE,
        elo=elo,
        opponent_elo=opponent_elo,
        coach_enabled=coach_enabled,
        movetime_ms=movetime_ms or settings.movetime_ms,
    )
    app.run()
    return 0
