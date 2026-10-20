from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk

import chess

from stockfeet import __version__
from stockfeet.config import Settings
from stockfeet.legal import SHORT_CREDIT
from stockfeet.profile import Profile
from stockfeet.path import (
    PATH_STAGES,
    apply_path_solve,
    get_stage,
    path_complete,
    skip_to_stage,
    stage_progress_label,
)
from stockfeet.path_view import PathMapView
from stockfeet.puzzles import (
    PuzzleSession,
    pick_puzzle,
    pick_puzzle_for_path,
    puzzle_count,
    themes_available,
)
from stockfeet.rewards import puzzle_reward
from stockfeet.shop import (
    BOARD_SKINS,
    PIECE_SKINS,
    board_colors,
    buy,
    equip,
    piece_colors,
)
from stockfeet.strength import strength_for_elo


BG = "#14181c"
PANEL = "#1c2329"
CARD = "#243039"
FG = "#f3f6f8"
MUTED = "#9aabb8"
ACCENT = "#f0c75e"
ACCENT_DIM = "#c4a04a"
OK = "#58cc02"
HEADER_BG = "#0e1216"


class Hub(tk.Tk):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.profile = Profile.load()
        self.puzzle_total = puzzle_count()
        self.title(f"Stockfeet {__version__}")
        self.configure(background=BG)
        self.geometry("1280x760")
        self.minsize(1040, 640)

        self.coins_var = tk.StringVar()
        self.xp_var = tk.StringVar()
        self.streak_var = tk.StringVar()
        self._refresh_header_vars()

        self._build()

    def _refresh_header_vars(self) -> None:
        self.coins_var.set(f"FeetCoins: {self.profile.coins}")
        self.xp_var.set(f"XP: {self.profile.xp}")
        self.streak_var.set(f"Streak: {self.profile.streak} (best {self.profile.best_streak})")

    def _build(self) -> None:
        header = tk.Frame(self, background=HEADER_BG, padx=14, pady=12)
        header.pack(fill=tk.X)
        brand = tk.Frame(header, background=HEADER_BG)
        brand.pack(side=tk.LEFT)
        tk.Label(brand, text="Stockfeet", font=("Segoe UI", 20, "bold"), fg=ACCENT, bg=HEADER_BG).pack(
            anchor="w"
        )
        tk.Label(
            brand,
            text="lc0 coach · puzzles · skins",
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=HEADER_BG,
        ).pack(anchor="w")
        stats = tk.Frame(header, background=HEADER_BG)
        stats.pack(side=tk.RIGHT)
        for var in (self.coins_var, self.xp_var, self.streak_var):
            chip = tk.Frame(stats, background=CARD, padx=10, pady=4)
            chip.pack(side=tk.RIGHT, padx=4)
            tk.Label(chip, textvariable=var, font=("Segoe UI", 10, "bold"), fg=FG, bg=CARD).pack()

        tk.Label(self, text=SHORT_CREDIT, font=("Segoe UI", 8), fg="#667788", bg=BG).pack(
            anchor="w", padx=14, pady=(4, 0)
        )

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=[14, 8], font=("Segoe UI", 10, "bold"))

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.play_tab = tk.Frame(nb, background=BG)
        self.puzzle_tab = tk.Frame(nb, background=BG)
        self.shop_tab = tk.Frame(nb, background=BG)
        self.profile_tab = tk.Frame(nb, background=BG)
        nb.add(self.play_tab, text="  Play  ")
        nb.add(self.puzzle_tab, text="  Puzzles  ")
        nb.add(self.shop_tab, text="  Shop  ")
        nb.add(self.profile_tab, text="  Profile  ")

        self._build_play_tab()
        self._build_puzzle_tab()
        self._build_shop_tab()
        self._build_profile_tab()

        nb.bind("<<NotebookTabChanged>>", lambda _e: self._on_tab())

    def _on_tab(self) -> None:
        self.profile = Profile.load()
        self._refresh_header_vars()
        self._render_shop()
        self._render_profile()

    def _build_play_tab(self) -> None:
        f = self.play_tab
        hero = tk.Frame(f, background=PANEL, padx=18, pady=16)
        hero.pack(fill=tk.X, padx=12, pady=12)
        tk.Label(
            hero,
            text="Play vs Leela",
            font=("Segoe UI", 18, "bold"),
            fg=ACCENT,
            bg=PANEL,
        ).pack(anchor="w")
        tk.Label(
            hero,
            text="Pick a strength card — lc0 is limited to match that Elo (not full engine play).",
            fg=MUTED,
            bg=PANEL,
        ).pack(anchor="w", pady=(4, 0))
        if not self.settings.lc0_ready:
            warn = tk.Frame(f, background="#3b1d1d", padx=14, pady=10)
            warn.pack(fill=tk.X, padx=12, pady=(0, 8))
            tk.Label(
                warn,
                text=(
                    "lc0 not found — Play/Demo need the engine.\n"
                    f"Expected: {self.settings.lc0_path}\n"
                    "Download from https://lczero.org/play/download/ and set STOCKFEET_LC0_PATH in .env.\n"
                    "Puzzles, path, shop and profile still work."
                ),
                fg="#ffb4b4",
                bg="#3b1d1d",
                justify="left",
            ).pack(anchor="w")

        self.play_color = tk.StringVar(value="white")
        self.play_elo = tk.IntVar(value=self.profile.puzzle_rating)
        self.opponent_elo = tk.IntVar(value=min(1800, max(800, self.profile.puzzle_rating)))
        self.opp_desc = tk.StringVar()

        cards = tk.Frame(f, background=BG)
        cards.pack(fill=tk.X, padx=12, pady=(0, 8))
        presets = (
            ("Beginner", 800, "Human beginner, not random"),
            ("Club", 1200, "Solid basics, uneven"),
            ("Strong club", 1500, "Finds most one-movers"),
            ("Expert", 1800, "Sharp but human"),
            ("Master", 2100, "Rarely hangs pieces"),
            ("Full lc0", 2800, "Raw engine strength"),
        )
        for i, (label, elo, blurb) in enumerate(presets):
            card = tk.Frame(cards, background=CARD, padx=12, pady=10)
            card.grid(row=0, column=i, padx=4, sticky="nsew")
            cards.grid_columnconfigure(i, weight=1)
            tk.Label(card, text=label, font=("Segoe UI", 11, "bold"), fg=FG, bg=CARD).pack(anchor="w")
            tk.Label(card, text=f"~{elo} Elo", font=("Segoe UI", 14, "bold"), fg=ACCENT, bg=CARD).pack(
                anchor="w"
            )
            tk.Label(card, text=blurb, font=("Segoe UI", 8), fg=MUTED, bg=CARD, wraplength=120).pack(
                anchor="w", pady=(4, 6)
            )
            tk.Button(
                card,
                text="Select",
                command=lambda e=elo: self._select_opponent(e),
                bg=ACCENT_DIM,
                fg="#1a1200",
                relief=tk.FLAT,
                padx=8,
            ).pack(anchor="w")

        opts = tk.Frame(f, background=PANEL, padx=16, pady=12)
        opts.pack(fill=tk.X, padx=12, pady=8)
        tk.Label(opts, text="Your color", fg=MUTED, bg=PANEL).grid(row=0, column=0, sticky="w")
        ttk.Combobox(opts, textvariable=self.play_color, values=["white", "black", "random"], width=10).grid(
            row=0, column=1, padx=8
        )
        tk.Label(opts, text="Opponent Elo", fg=MUTED, bg=PANEL).grid(row=0, column=2, sticky="w", padx=(16, 0))
        tk.Spinbox(opts, from_=600, to=2800, increment=25, textvariable=self.opponent_elo, width=8,
                   command=self._refresh_opp_desc).grid(row=0, column=3, padx=8)
        self.opponent_elo.trace_add("write", lambda *_: self._refresh_opp_desc())
        tk.Label(opts, text="Coach tone Elo", fg=MUTED, bg=PANEL).grid(row=1, column=0, sticky="w", pady=(10, 0))
        tk.Spinbox(opts, from_=600, to=2800, increment=50, textvariable=self.play_elo, width=8).grid(
            row=1, column=1, padx=8, pady=(10, 0)
        )
        tk.Label(opts, textvariable=self.opp_desc, fg=FG, bg=PANEL, wraplength=640, justify="left").grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(12, 0)
        )

        tk.Button(
            f,
            text="Start game",
            font=("Segoe UI", 13, "bold"),
            command=self._start_game,
            bg=OK,
            fg="#0d1f0d",
            relief=tk.FLAT,
            padx=22,
            pady=10,
        ).pack(side=tk.LEFT, padx=(12, 6), pady=10)
        tk.Button(
            f,
            text="Watch AI demo",
            font=("Segoe UI", 12, "bold"),
            command=self._start_ai_demo,
            bg=ACCENT_DIM,
            fg="#1a1200",
            relief=tk.FLAT,
            padx=16,
            pady=10,
        ).pack(side=tk.LEFT, pady=10)
        tk.Label(
            f,
            text="Demo = both sides at the selected Elo (so you can judge strength without being 1500+).",
            fg=MUTED,
            bg=BG,
            wraplength=700,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 10))
        self._refresh_opp_desc()

    def _select_opponent(self, elo: int) -> None:
        self.opponent_elo.set(elo)
        self._refresh_opp_desc()

    def _refresh_opp_desc(self) -> None:
        try:
            elo = int(self.opponent_elo.get())
        except (tk.TclError, ValueError):
            return
        cfg = strength_for_elo(elo)
        if elo >= 2750:
            self.opp_desc.set("Strength: full lc0 best-move play (no human limiter).")
            return
        self.opp_desc.set(
            f"Limiter ~{cfg.elo} Elo · think {cfg.movetime_ms}ms · MultiPV {cfg.multipv} · "
            f"best-move rate ≈ {cfg.target_best_rate:.0%} · noise ±{cfg.noise_sigma_cp:.0f}cp · "
            f"max slip ~{cfg.max_loss_cp:.0f}cp"
        )

    def _start_game(self) -> None:
        import random

        from stockfeet.gui import StockfeetApp

        try:
            self.settings.require_lc0()
        except FileNotFoundError as exc:
            messagebox.showerror("lc0 missing", str(exc))
            return

        color = self.play_color.get()
        if color == "random":
            color = random.choice(("white", "black"))
        human = chess.WHITE if color == "white" else chess.BLACK
        opp = int(self.opponent_elo.get())
        win = tk.Toplevel(self)
        win.title(f"Stockfeet — Play ({color}) vs ~{opp} Elo")
        StockfeetApp(
            self.settings,
            human_color=human,
            elo=int(self.play_elo.get()),
            opponent_elo=opp,
            coach_enabled=True,
            movetime_ms=self.settings.movetime_ms,
            master=win,
            profile=self.profile,
            autoplay=False,
        )

    def _start_ai_demo(self) -> None:
        from stockfeet.gui import StockfeetApp

        try:
            self.settings.require_lc0()
        except FileNotFoundError as exc:
            messagebox.showerror("lc0 missing", str(exc))
            return

        opp = int(self.opponent_elo.get())
        win = tk.Toplevel(self)
        win.title(f"Stockfeet — AI demo ~{opp} Elo")
        StockfeetApp(
            self.settings,
            human_color=chess.WHITE,
            elo=int(self.play_elo.get()),
            opponent_elo=opp,
            coach_enabled=False,
            movetime_ms=self.settings.movetime_ms,
            master=win,
            profile=self.profile,
            autoplay=True,
        )

    def _build_puzzle_tab(self) -> None:
        f = self.puzzle_tab
        top = tk.Frame(f, background=BG)
        top.pack(fill=tk.X, padx=12, pady=10)

        tk.Label(top, text="Puzzles", fg=FG, bg=BG, font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)

        self.path_mode = tk.BooleanVar(value=self.profile.path_mode)
        tk.Checkbutton(
            top,
            text="Learning path",
            variable=self.path_mode,
            command=self._on_path_mode_toggle,
            fg=FG,
            bg=BG,
            selectcolor="#333",
            activebackground=BG,
            activeforeground=FG,
        ).pack(side=tk.LEFT, padx=12)

        tk.Button(top, text="New puzzle", command=self._new_puzzle).pack(side=tk.RIGHT)
        tk.Button(top, text="Restart path", command=self._restart_path).pack(side=tk.RIGHT, padx=6)

        themes = ["all", *themes_available()]
        self.theme_var = tk.StringVar(value="all")
        self.theme_combo = ttk.Combobox(top, textvariable=self.theme_var, values=themes, width=16)
        self.theme_combo.pack(side=tk.RIGHT, padx=6)
        self.theme_label = tk.Label(top, text="Theme:", fg="#aaa", bg=BG)
        self.theme_label.pack(side=tk.RIGHT)

        # Free-practice Elo row (hidden visuals while on path)
        self.filt = tk.Frame(f, background=BG)
        self.filt.pack(fill=tk.X, padx=12, pady=(0, 6))
        self.puzzle_elo = tk.IntVar(value=self.profile.puzzle_rating)
        self.elo_label = tk.Label(self.filt, text="Puzzle Elo:", fg=FG, bg=BG)
        self.elo_label.pack(side=tk.LEFT)
        self.elo_spin = tk.Spinbox(
            self.filt, from_=600, to=2600, increment=50, textvariable=self.puzzle_elo, width=8
        )
        self.elo_spin.pack(side=tk.LEFT, padx=6)
        self.elo_preset_btns: list[tk.Button] = []
        for label, elo in (
            ("800", 800),
            ("1100", 1100),
            ("1400", 1400),
            ("1700", 1700),
            ("2000", 2000),
            ("2300", 2300),
        ):
            btn = tk.Button(self.filt, text=label, command=lambda e=elo: self._set_puzzle_elo(e))
            btn.pack(side=tk.LEFT, padx=2)
            self.elo_preset_btns.append(btn)
        tk.Label(
            self.filt,
            text=f"({self.puzzle_total:,} puzzles)",
            fg="#888",
            bg=BG,
        ).pack(side=tk.LEFT, padx=8)

        body = tk.Frame(f, background=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # Left: Duolingo-style path map
        self.path_pane = tk.Frame(body, background="#122018", width=320)
        self.path_pane.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        self.path_pane.pack_propagate(False)
        self.path_map = PathMapView(self.path_pane, on_select=self._on_path_node, width=300)
        self.path_map.pack(fill=tk.BOTH, expand=True)

        # Right: board + lesson controls
        self.puzzle_right = tk.Frame(body, background=BG)
        self.puzzle_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        lesson = tk.Frame(self.puzzle_right, background="#252525", padx=10, pady=8)
        lesson.pack(fill=tk.X, pady=(0, 6))
        self.path_progress = tk.StringVar()
        self.path_blurb = tk.StringVar()
        tk.Label(
            lesson,
            textvariable=self.path_progress,
            font=("Segoe UI", 12, "bold"),
            fg=ACCENT,
            bg="#252525",
        ).pack(anchor="w")
        tk.Label(
            lesson,
            textvariable=self.path_blurb,
            fg="#ccc",
            bg="#252525",
            wraplength=520,
            justify="left",
        ).pack(anchor="w")
        lesson_btns = tk.Frame(lesson, background="#252525")
        lesson_btns.pack(anchor="w", pady=(8, 0))
        self.skip_stage_btn = tk.Button(
            lesson_btns, text="Skip this stage →", command=self._skip_current_stage
        )
        self.skip_stage_btn.pack(side=tk.LEFT)
        self.jump_btn = tk.Button(lesson_btns, text="Jump…", command=self._jump_dialog)
        self.jump_btn.pack(side=tk.LEFT, padx=6)

        play_row = tk.Frame(self.puzzle_right, background=BG)
        play_row.pack(fill=tk.BOTH, expand=True)

        from stockfeet.gui import BoardCanvas

        bc = board_colors(self.profile.equipped_board)
        pc = piece_colors(self.profile.equipped_pieces)

        self.puzzle_board = BoardCanvas(
            play_row,
            perspective_white=True,
            on_square=self._on_puzzle_square,
            light=bc[0],
            dark=bc[1],
            piece_white=pc[0],
            piece_black=pc[1],
        )
        self.puzzle_board.pack(side=tk.LEFT)

        side = tk.Frame(play_row, background=BG)
        side.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12)
        self.puzzle_title = tk.StringVar(value="Click New puzzle")
        self.puzzle_meta = tk.StringVar(value="")
        self.puzzle_status = tk.StringVar(value="")
        tk.Label(side, textvariable=self.puzzle_title, font=("Segoe UI", 14, "bold"), fg=ACCENT, bg=BG).pack(
            anchor="w"
        )
        tk.Label(side, textvariable=self.puzzle_meta, fg="#ccc", bg=BG, wraplength=320, justify="left").pack(
            anchor="w", pady=6
        )
        tk.Label(side, textvariable=self.puzzle_status, fg=FG, bg=BG, wraplength=320, justify="left").pack(
            anchor="w", pady=6
        )
        btns = tk.Frame(side, background=BG)
        btns.pack(anchor="w", pady=10)
        tk.Button(btns, text="Hint (−5 coins)", command=self._puzzle_hint).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btns, text="Skip puzzle", command=self._new_puzzle).pack(side=tk.LEFT)

        self._puzzle_session: PuzzleSession | None = None
        self._puzzle_selected: chess.Square | None = None
        self._puzzle_started = 0.0
        self._play_stage_override: int | None = None
        self._refresh_path_ui()
        self._sync_free_controls()
        self._new_puzzle()

    def _on_path_mode_toggle(self) -> None:
        self.profile.path_mode = bool(self.path_mode.get())
        self.profile.save()
        self._play_stage_override = None
        self._refresh_path_ui()
        self._sync_free_controls()
        self._new_puzzle()

    def _sync_free_controls(self) -> None:
        on_path = bool(self.path_mode.get())
        if on_path:
            if not self.path_pane.winfo_ismapped():
                self.path_pane.pack(
                    side=tk.LEFT, fill=tk.Y, padx=(0, 8), before=self.puzzle_right
                )
            self.path_pane.configure(width=320)
            self.path_pane.pack_propagate(False)
            self.filt.pack_forget()
            self.theme_combo.pack_forget()
            self.theme_label.pack_forget()
            self.skip_stage_btn.configure(state=tk.NORMAL)
            self.jump_btn.configure(state=tk.NORMAL)
        else:
            self.path_pane.pack_forget()
            children = self.puzzle_tab.winfo_children()
            if not self.filt.winfo_ismapped():
                if children:
                    self.filt.pack(fill=tk.X, padx=12, pady=(0, 6), after=children[0])
                else:
                    self.filt.pack(fill=tk.X, padx=12, pady=(0, 6))
            self.theme_label.pack(side=tk.RIGHT)
            self.theme_combo.pack(side=tk.RIGHT, padx=6)
            self.theme_combo.configure(state="readonly")
            self.elo_spin.configure(state=tk.NORMAL)
            for btn in self.elo_preset_btns:
                btn.configure(state=tk.NORMAL)
            self.skip_stage_btn.configure(state=tk.DISABLED)
            self.jump_btn.configure(state=tk.DISABLED)

    def _refresh_path_ui(self) -> None:
        idx = self.profile.path_stage
        solved = self.profile.path_stage_solved
        self.path_progress.set(stage_progress_label(idx, solved))
        self.path_map.set_state(idx, solved, self.profile.path_skipped)
        if path_complete(idx):
            self.path_blurb.set(
                "You cleared every stage. Replay any node, free-practice, or restart the path."
            )
            return
        stage = get_stage(idx)
        themes = ", ".join(stage.themes) if stage.themes else "any theme"
        self.path_blurb.set(
            f"{stage.blurb}  ·  ~{stage.rating} Elo  ·  {themes}\n"
            "Tap a node ahead to skip there, or use Skip this stage."
        )

    def _on_path_node(self, index: int) -> None:
        if not bool(self.path_mode.get()):
            self.path_mode.set(True)
            self.profile.path_mode = True
        cur = self.profile.path_stage
        if path_complete(cur) and index < len(PATH_STAGES):
            # Replay a finished stage without changing completion cursor unless user wants
            if messagebox.askyesno(
                "Replay stage",
                f"Replay “{PATH_STAGES[index].name}”? Progress cursor stays at the end.",
            ):
                # Temporarily play that stage's puzzles without moving cursor:
                self._play_stage_override = index
                self._new_puzzle()
            return

        if index == cur:
            self._play_stage_override = None
            self._new_puzzle()
            return

        if index < cur:
            stage = PATH_STAGES[index]
            if messagebox.askyesno(
                "Go back",
                f"Go back to “{stage.name}”?\n\n"
                "Your path cursor moves there. Later stages become available again ahead of you.",
            ):
                self.profile.path_stage = index
                self.profile.path_stage_solved = 0
                ahead_ids = {PATH_STAGES[i].id for i in range(index, len(PATH_STAGES))}
                self.profile.path_skipped = [
                    s for s in self.profile.path_skipped if s not in ahead_ids
                ]
                self._play_stage_override = None
                self.profile.save()
                self._refresh_path_ui()
                self._new_puzzle()
            return

        # Jump ahead = skip
        stage = PATH_STAGES[index]
        if messagebox.askyesno(
            "Skip to stage",
            f"Skip ahead to “{stage.name}” (~{stage.rating} Elo)?\n\n"
            f"Stages in between will be marked as skipped (you can still go back).",
        ):
            new_idx, new_solved, skipped = skip_to_stage(
                current_index=cur,
                target_index=index,
                skipped_ids=self.profile.path_skipped,
            )
            self.profile.path_stage = new_idx
            self.profile.path_stage_solved = new_solved
            self.profile.path_skipped = skipped
            self._play_stage_override = None
            self.profile.save()
            self._refresh_path_ui()
            self._new_puzzle()

    def _skip_current_stage(self) -> None:
        if path_complete(self.profile.path_stage):
            messagebox.showinfo("Path", "Path already complete.")
            return
        nxt = self.profile.path_stage + 1
        if nxt >= len(PATH_STAGES):
            label = "finish the path (mark last stage skipped)"
        else:
            label = f"jump to “{PATH_STAGES[nxt].name}”"
        if not messagebox.askyesno("Skip stage", f"Skip this stage and {label}?"):
            return
        new_idx, new_solved, skipped = skip_to_stage(
            current_index=self.profile.path_stage,
            target_index=nxt,
            skipped_ids=self.profile.path_skipped,
        )
        self.profile.path_stage = new_idx
        self.profile.path_stage_solved = new_solved
        self.profile.path_skipped = skipped
        self._play_stage_override = None
        self.profile.save()
        self._refresh_path_ui()
        self._sync_free_controls()
        self._new_puzzle()

    def _jump_dialog(self) -> None:
        win = tk.Toplevel(self)
        win.title("Jump to stage")
        win.configure(background=BG)
        win.geometry("360x420")
        tk.Label(win, text="Choose a stage", fg=FG, bg=BG, font=("Segoe UI", 12, "bold")).pack(
            pady=10
        )
        box = tk.Listbox(win, font=("Segoe UI", 10), height=16)
        box.pack(fill=tk.BOTH, expand=True, padx=12)
        cur = self.profile.path_stage
        for i, stage in enumerate(PATH_STAGES):
            mark = "✓" if i < cur else ("▶" if i == cur else "·")
            if stage.id in self.profile.path_skipped and i >= cur:
                mark = "↷"
            box.insert(tk.END, f"{mark} {i + 1}. {stage.name}  (~{stage.rating})")
        if not path_complete(cur):
            box.selection_set(cur)
            box.see(cur)

        def go() -> None:
            sel = box.curselection()
            if not sel:
                return
            win.destroy()
            self._on_path_node(int(sel[0]))

        tk.Button(win, text="Go", command=go).pack(pady=10)

    def _restart_path(self) -> None:
        if not messagebox.askyesno("Restart path", "Reset path progress to First checks?"):
            return
        self.profile.path_stage = 0
        self.profile.path_stage_solved = 0
        self.profile.path_skipped = []
        self.profile.path_mode = True
        self.path_mode.set(True)
        self._play_stage_override = None
        self.profile.save()
        self._refresh_path_ui()
        self._sync_free_controls()
        self._new_puzzle()

    def _set_puzzle_elo(self, elo: int) -> None:
        self.puzzle_elo.set(elo)
        self._new_puzzle()

    def _active_path_stage_index(self) -> int | None:
        if not bool(self.path_mode.get()):
            return None
        if getattr(self, "_play_stage_override", None) is not None:
            return int(self._play_stage_override)
        if path_complete(self.profile.path_stage):
            return None
        return self.profile.path_stage

    def _new_puzzle(self) -> None:
        exclude = set(self.profile.solved_puzzle_ids[-120:])
        stage_idx = self._active_path_stage_index()

        if stage_idx is not None:
            stage = get_stage(stage_idx)
            target = stage.rating
            self.puzzle_elo.set(target)
            puzzle = pick_puzzle_for_path(
                rating=target,
                themes=stage.themes,
                exclude_ids=exclude,
            )
            mode_note = f"Path · {stage.name}"
        else:
            theme = self.theme_var.get()
            target = int(self.puzzle_elo.get())
            puzzle = pick_puzzle(rating=target, theme=theme, exclude_ids=exclude)
            mode_note = "Free practice"

        if puzzle is None:
            self.puzzle_status.set("No puzzles for that filter.")
            return
        self._puzzle_session = PuzzleSession(puzzle)
        self._puzzle_selected = None
        self._puzzle_started = time.time()
        stm = self._puzzle_session.board.turn
        self.puzzle_board.perspective_white = stm == chess.WHITE
        self.puzzle_board.set_selection(None)
        self.puzzle_board.set_last_move(None)
        self.puzzle_board.draw(self._puzzle_session.board)
        self.puzzle_title.set(puzzle.title)
        self.puzzle_meta.set(
            f"{mode_note} · Lichess {puzzle.rating} (target ~{target}) · "
            f"Themes: {', '.join(puzzle.themes[:6])}"
        )
        side = "White" if stm == chess.WHITE else "Black"
        self.puzzle_status.set(f"Your turn ({side}). Click piece → destination.")
        self._refresh_path_ui()
    def _on_puzzle_square(self, square: chess.Square) -> None:
        session = self._puzzle_session
        if session is None or session.finished:
            return
        board = session.board
        if self._puzzle_selected is None:
            piece = board.piece_at(square)
            if piece is None or piece.color != board.turn:
                return
            self._puzzle_selected = square
            targets = {m.to_square for m in board.legal_moves if m.from_square == square}
            self.puzzle_board.set_selection(square, targets)
            self.puzzle_board.draw(board)
            return
        if square == self._puzzle_selected:
            self._puzzle_selected = None
            self.puzzle_board.set_selection(None)
            self.puzzle_board.draw(board)
            return
        move = self._match_move(board, self._puzzle_selected, square)
        self._puzzle_selected = None
        self.puzzle_board.set_selection(None)
        if move is None:
            self.puzzle_board.draw(board)
            return
        result = session.try_move(move)
        self.puzzle_board.set_last_move(move)
        self.puzzle_board.draw(session.board)
        if result == "wrong":
            self.puzzle_status.set("Not the idea — try again.")
            return
        if result in {"ok", "solved"} and result != "solved":
            self.puzzle_status.set("Good! Continue the line…" if not session.finished else "")
        if session.finished and session.success:
            self._reward_success(session)

    def _match_move(self, board: chess.Board, frm: chess.Square, to: chess.Square) -> chess.Move | None:
        candidates = [m for m in board.legal_moves if m.from_square == frm and m.to_square == to]
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        for m in candidates:
            if m.promotion == chess.QUEEN:
                return m
        return candidates[0]

    def _reward_success(self, session: PuzzleSession) -> None:
        seconds = max(1.0, time.time() - self._puzzle_started)
        first_try = session.wrong_attempts == 0
        self.profile.streak += 1
        self.profile.best_streak = max(self.profile.best_streak, self.profile.streak)
        self.profile.puzzles_solved += 1
        if session.puzzle.id not in self.profile.solved_puzzle_ids:
            self.profile.solved_puzzle_ids.append(session.puzzle.id)
        # Soft rating drift toward puzzle rating.
        self.profile.puzzle_rating += max(
            -15, min(20, (session.puzzle.rating - self.profile.puzzle_rating) // 10 + 5)
        )
        reward = puzzle_reward(
            rating=session.puzzle.rating,
            perfect=session.perfect,
            first_try=first_try,
            streak_after=self.profile.streak,
            seconds=seconds,
        )
        self.profile.coins += reward.coins
        self.profile.xp += reward.xp

        path_msg = ""
        counting_path = (
            bool(self.path_mode.get())
            and self._play_stage_override is None
            and not path_complete(self.profile.path_stage)
        )
        if counting_path:
            cleared_id = get_stage(self.profile.path_stage).id
            new_idx, new_solved, cleared, bonus = apply_path_solve(
                stage_index=self.profile.path_stage,
                solved_in_stage=self.profile.path_stage_solved,
                perfect=session.perfect,
            )
            self.profile.path_stage = new_idx
            self.profile.path_stage_solved = new_solved
            self.profile.coins += bonus
            if cleared and cleared_id in self.profile.path_skipped:
                self.profile.path_skipped = [
                    s for s in self.profile.path_skipped if s != cleared_id
                ]
            if cleared:
                if path_complete(new_idx):
                    path_msg = f"\n\nPath complete! +{bonus} path bonus."
                else:
                    nxt = get_stage(new_idx)
                    path_msg = (
                        f"\n\nStage cleared! Next: {nxt.name} (~{nxt.rating}). "
                        f"+{bonus} path bonus."
                    )
            else:
                stage = get_stage(new_idx)
                path_msg = (
                    f"\n\nPath: {new_solved}/{stage.needed} in {stage.name} "
                    f"(+{bonus} path coins)."
                )

        self.profile.save()
        self._refresh_header_vars()
        self._refresh_path_ui()
        self._sync_free_controls()
        self.puzzle_status.set(f"Solved! {reward.message}")
        messagebox.showinfo("Puzzle solved", reward.message + path_msg)

    def _puzzle_hint(self) -> None:
        session = self._puzzle_session
        if session is None or session.finished:
            return
        if self.profile.coins < 5:
            messagebox.showwarning("Hint", "Need 5 FeetCoins for a hint.")
            return
        self.profile.coins -= 5
        self.profile.save()
        self._refresh_header_vars()
        session.perfect = False
        expected = session.expected_move()
        hint = session.puzzle.hint
        if expected:
            hint = f"{hint}\nLook at {chess.SQUARE_NAMES[expected.from_square]}…"
        self.puzzle_status.set(hint)

    def _build_shop_tab(self) -> None:
        root = self.shop_tab
        top = tk.Frame(root, background=PANEL, padx=14, pady=12)
        top.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(top, text="Skin shop", font=("Segoe UI", 16, "bold"), fg=ACCENT, bg=PANEL).pack(
            anchor="w"
        )
        tk.Label(
            top,
            text="Preview any board + pieces combo before buying. Cosmetics only.",
            fg=MUTED,
            bg=PANEL,
        ).pack(anchor="w")

        body = tk.Frame(root, background=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Catalog (scrollable)
        left_wrap = tk.Frame(body, background=BG)
        left_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(left_wrap, background=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(left_wrap, orient=tk.VERTICAL, command=canvas.yview)
        self.shop_list = tk.Frame(canvas, background=BG)
        self.shop_list.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.shop_list, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Live preview
        preview = tk.Frame(body, background=PANEL, padx=14, pady=14)
        preview.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        tk.Label(preview, text="Preview", font=("Segoe UI", 12, "bold"), fg=FG, bg=PANEL).pack(
            anchor="w"
        )
        self.preview_board_id = tk.StringVar(value=self.profile.equipped_board)
        self.preview_piece_id = tk.StringVar(value=self.profile.equipped_pieces)
        self.preview_label = tk.StringVar()
        tk.Label(
            preview,
            textvariable=self.preview_label,
            fg=MUTED,
            bg=PANEL,
            wraplength=260,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        from stockfeet.gui import BoardCanvas

        bc = board_colors(self.preview_board_id.get())
        pc = piece_colors(self.preview_piece_id.get())
        self.shop_preview = BoardCanvas(
            preview,
            perspective_white=True,
            on_square=None,
            light=bc[0],
            dark=bc[1],
            piece_white=pc[0],
            piece_black=pc[1],
            board_size=280,
            interactive=False,
        )
        self.shop_preview.pack()
        self._preview_board = chess.Board()
        # A lively middlegame-ish preview setup
        self._preview_board.set_fen(
            "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        )
        self.shop_preview.draw(self._preview_board)

        actions = tk.Frame(preview, background=PANEL)
        actions.pack(fill=tk.X, pady=(12, 0))
        tk.Button(
            actions,
            text="Equip preview combo",
            command=self._equip_preview_combo,
            bg=OK,
            fg="#0d1f0d",
            relief=tk.FLAT,
            padx=10,
            pady=6,
        ).pack(fill=tk.X)
        tk.Button(
            actions,
            text="Reset to equipped",
            command=self._reset_preview_to_equipped,
            relief=tk.FLAT,
            padx=10,
            pady=4,
        ).pack(fill=tk.X, pady=(6, 0))

        self._render_shop()

    def _reset_preview_to_equipped(self) -> None:
        self.preview_board_id.set(self.profile.equipped_board)
        self.preview_piece_id.set(self.profile.equipped_pieces)
        self._update_shop_preview()

    def _equip_preview_combo(self) -> None:
        bid = self.preview_board_id.get()
        pid = self.preview_piece_id.get()
        msgs: list[str] = []
        from stockfeet.shop import get_skin

        for skin_id, kind in ((bid, "board"), (pid, "pieces")):
            skin = get_skin(skin_id, kind)
            if skin is None:
                continue
            owned = self.profile.owns_board(skin_id) if kind == "board" else self.profile.owns_pieces(skin_id)
            if not owned:
                msgs.append(f"Buy {skin.name} first.")
                continue
            msgs.append(equip(self.profile, skin))
        self.profile = Profile.load()
        self._refresh_header_vars()
        self._apply_equipped_to_puzzle_board()
        self._render_shop()
        messagebox.showinfo("Shop", "\n".join(msgs) if msgs else "Nothing to equip.")

    def _preview_skin(self, skin) -> None:  # noqa: ANN001
        if skin.kind == "board":
            self.preview_board_id.set(skin.id)
        else:
            self.preview_piece_id.set(skin.id)
        self._update_shop_preview()

    def _update_shop_preview(self) -> None:
        bc = board_colors(self.preview_board_id.get())
        pc = piece_colors(self.preview_piece_id.get())
        self.shop_preview.apply_skin(
            light=bc[0], dark=bc[1], piece_white=pc[0], piece_black=pc[1]
        )
        self.shop_preview.draw(self._preview_board)
        self.preview_label.set(
            f"Board: {self.preview_board_id.get()}  ·  Pieces: {self.preview_piece_id.get()}"
        )

    def _render_shop(self) -> None:
        if not hasattr(self, "shop_list"):
            return
        for child in self.shop_list.winfo_children():
            child.destroy()

        def section(title: str) -> None:
            tk.Label(
                self.shop_list,
                text=title,
                font=("Segoe UI", 12, "bold"),
                fg=ACCENT,
                bg=BG,
            ).pack(anchor="w", pady=(8, 4))

        section("Boards")
        for skin in BOARD_SKINS:
            self._shop_skin_row(skin)
        section("Pieces")
        for skin in PIECE_SKINS:
            self._shop_skin_row(skin)
        self._update_shop_preview()

    def _shop_skin_row(self, skin) -> None:  # noqa: ANN001
        owned = (
            self.profile.owns_board(skin.id)
            if skin.kind == "board"
            else self.profile.owns_pieces(skin.id)
        )
        equipped = (
            self.profile.equipped_board == skin.id
            if skin.kind == "board"
            else self.profile.equipped_pieces == skin.id
        )
        row = tk.Frame(self.shop_list, background=CARD, padx=10, pady=8)
        row.pack(fill=tk.X, pady=3, padx=2)

        # Color swatch
        if skin.kind == "board":
            c0, c1 = board_colors(skin.id)
        else:
            c0, c1 = piece_colors(skin.id)
        sw = tk.Canvas(row, width=44, height=28, highlightthickness=0, background=CARD)
        sw.pack(side=tk.LEFT, padx=(0, 10))
        sw.create_rectangle(0, 0, 22, 28, fill=c0, outline="")
        sw.create_rectangle(22, 0, 44, 28, fill=c1, outline="")

        text = tk.Frame(row, background=CARD)
        text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(text, text=skin.name, fg=FG, bg=CARD, font=("Segoe UI", 10, "bold"), anchor="w").pack(
            anchor="w"
        )
        tk.Label(text, text=skin.description, fg=MUTED, bg=CARD, font=("Segoe UI", 8), anchor="w").pack(
            anchor="w"
        )

        status = "EQUIPPED" if equipped else ("OWNED" if owned else f"{skin.price} ¢")
        tk.Label(row, text=status, fg=ACCENT, bg=CARD, font=("Segoe UI", 9, "bold")).pack(
            side=tk.RIGHT, padx=6
        )
        tk.Button(row, text="Preview", command=lambda s=skin: self._preview_skin(s), relief=tk.FLAT).pack(
            side=tk.RIGHT, padx=2
        )
        if not owned:
            tk.Button(row, text="Buy", command=lambda s=skin: self._buy(s), bg=ACCENT_DIM, relief=tk.FLAT).pack(
                side=tk.RIGHT, padx=2
            )
        elif not equipped:
            tk.Button(row, text="Equip", command=lambda s=skin: self._equip(s), relief=tk.FLAT).pack(
                side=tk.RIGHT, padx=2
            )

    def _buy(self, skin) -> None:  # noqa: ANN001
        msg = buy(self.profile, skin)
        self.profile = Profile.load()
        self._refresh_header_vars()
        self._preview_skin(skin)
        self._render_shop()
        messagebox.showinfo("Shop", msg)

    def _equip(self, skin) -> None:  # noqa: ANN001
        msg = equip(self.profile, skin)
        self.profile = Profile.load()
        self._refresh_header_vars()
        self._preview_skin(skin)
        self._apply_equipped_to_puzzle_board()
        self._render_shop()
        messagebox.showinfo("Shop", msg)

    def _apply_equipped_to_puzzle_board(self) -> None:
        bc = board_colors(self.profile.equipped_board)
        pc = piece_colors(self.profile.equipped_pieces)
        self.puzzle_board.apply_skin(
            light=bc[0], dark=bc[1], piece_white=pc[0], piece_black=pc[1]
        )
        if self._puzzle_session:
            self.puzzle_board.draw(self._puzzle_session.board)

    def _build_profile_tab(self) -> None:
        self.profile_box = tk.Frame(self.profile_tab, background=BG)
        self.profile_box.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        self._render_profile()

    def _render_profile(self) -> None:
        for child in self.profile_box.winfo_children():
            child.destroy()
        p = self.profile
        path_line = stage_progress_label(p.path_stage, p.path_stage_solved)

        hero = tk.Frame(self.profile_box, background=PANEL, padx=16, pady=14)
        hero.pack(fill=tk.X, pady=(0, 10))
        tk.Label(hero, text="Your progress", font=("Segoe UI", 16, "bold"), fg=ACCENT, bg=PANEL).pack(
            anchor="w"
        )
        tk.Label(hero, text=path_line, fg=FG, bg=PANEL, font=("Segoe UI", 11)).pack(anchor="w", pady=(4, 0))

        stats = tk.Frame(self.profile_box, background=BG)
        stats.pack(fill=tk.X, pady=6)
        for title, value in (
            ("Puzzle Elo", str(p.puzzle_rating)),
            ("Solved", str(p.puzzles_solved)),
            ("Best streak", str(p.best_streak)),
            ("Board", p.equipped_board),
            ("Pieces", p.equipped_pieces),
        ):
            card = tk.Frame(stats, background=CARD, padx=12, pady=10)
            card.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
            tk.Label(card, text=title, fg=MUTED, bg=CARD, font=("Segoe UI", 8)).pack(anchor="w")
            tk.Label(card, text=value, fg=FG, bg=CARD, font=("Segoe UI", 12, "bold")).pack(anchor="w")

        tips = tk.Frame(self.profile_box, background=PANEL, padx=16, pady=14)
        tips.pack(fill=tk.BOTH, expand=True, pady=10)
        tk.Label(tips, text="How to improve", font=("Segoe UI", 13, "bold"), fg=FG, bg=PANEL).pack(
            anchor="w"
        )
        tip_lines = [
            "• Mate themes → pattern recognition",
            "• Forks / pins / skewers → tactics foundation",
            "• Endgames → conversion technique",
            "• Play vs lc0 after puzzles to apply ideas",
            "• Rewards: first try + perfect + speed + streak",
            "• Hints cost 5 FeetCoins and remove the perfect bonus",
        ]
        tk.Label(
            tips,
            text="\n".join(tip_lines),
            justify="left",
            fg=MUTED,
            bg=PANEL,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(8, 0))

        from stockfeet.coach.rules import improvement_plan

        plan = "\n".join(f"  • {x}" for x in improvement_plan(p.puzzle_rating))
        tk.Label(
            tips,
            text=f"\nPlan for ~{p.puzzle_rating} Elo:\n{plan}",
            justify="left",
            fg=FG,
            bg=PANEL,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(8, 0))


def run_hub(settings: Settings) -> int:
    app = Hub(settings)
    app.mainloop()
    return 0
