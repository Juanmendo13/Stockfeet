from __future__ import annotations

import argparse
import sys
from pathlib import Path

import chess

from stockfeet import __version__
from stockfeet.board_view import render_board
from stockfeet.coach import Coach
from stockfeet.coach.rules import classify_move, improvement_plan
from stockfeet.config import Settings
from stockfeet.engine import Lc0Engine
from stockfeet.game import GameSession
from stockfeet.legal import SHORT_CREDIT, about


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stockfeet",
        description="Stockfeet — play and learn with Leela Chess Zero (lc0).",
    )
    parser.add_argument("--version", action="version", version=f"Stockfeet {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("about", help="Show legal credits (lc0 GPL + Stockfeet MIT)")

    sub.add_parser(
        "setup-lc0",
        help="Download official Windows CPU lc0 into vendor/lc0 and write .env",
    )

    play = sub.add_parser("play", help="Play a game against lc0 (GUI window by default)")
    play.add_argument("--color", choices=("white", "black", "random"), default="white")
    play.add_argument("--elo", type=int, default=1200, help="Your approximate Elo (coaching tone)")
    play.add_argument("--no-coach", action="store_true", help="Skip per-move coaching")
    play.add_argument("--movetime", type=int, default=None, help="Override engine ms per move")
    play.add_argument(
        "--cli",
        action="store_true",
        help="Use PowerShell/terminal board instead of the graphical window",
    )
    play.add_argument(
        "--direct",
        action="store_true",
        help="Skip hub and open a single game window",
    )
    an = sub.add_parser("analyse", help="Analyse a FEN with lc0 + coach notes")
    an.add_argument("fen", nargs="?", default=chess.STARTING_FEN)
    an.add_argument("--elo", type=int, default=1200)
    an.add_argument("--movetime", type=int, default=None)

    lesson = sub.add_parser("lesson", help="Improvement plan for a given Elo")
    lesson.add_argument("--elo", type=int, default=1200)

    vs = sub.add_parser("engine-match", help="lc0 vs lc0 self-play (demo / testing)")
    vs.add_argument("--plies", type=int, default=40)
    vs.add_argument("--movetime", type=int, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "about":
        print(about(version=__version__))
        return 0

    if args.command == "setup-lc0":
        from stockfeet.setup_lc0 import ensure_lc0

        try:
            exe = ensure_lc0(progress=print)
        except Exception as exc:  # noqa: BLE001
            print(f"setup-lc0 failed: {exc}", file=sys.stderr)
            print("Manual download: https://lczero.org/play/download/", file=sys.stderr)
            return 1
        print(f"\nPowered by Leela Chess Zero — using {exe}")
        print("Run: stockfeet play")
        return 0

    if args.command == "lesson":
        coach = Coach(_settings_or_dummy(), student_elo=args.elo)
        print(coach.lesson_for_elo())
        return 0

    try:
        settings = Settings.from_env(require_engine=False)
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        print("See .env.example and NOTICE.", file=sys.stderr)
        return 2

    if args.command == "play":
        return cmd_play(settings, args)
    if args.command in {"analyse", "engine-match"}:
        try:
            settings.require_lc0()
        except FileNotFoundError as exc:
            print(f"Config error: {exc}", file=sys.stderr)
            return 2
    if args.command == "analyse":
        return cmd_analyse(settings, args)
    if args.command == "engine-match":
        return cmd_engine_match(settings, args)

    parser.error(f"Unknown command: {args.command}")
    return 2


def _settings_or_dummy() -> Settings:
    """Lesson command works without lc0 installed."""
    try:
        return Settings.from_env()
    except (RuntimeError, FileNotFoundError):
        return Settings(
            lc0_path=Path("lc0"),
            lc0_weights=None,
            movetime_ms=1000,
            openai_api_key=None,
            openai_base_url="https://api.openai.com/v1",
            openai_model="gpt-4o-mini",
        )


def cmd_play(settings: Settings, args: argparse.Namespace) -> int:
    import random

    if not args.cli:
        from stockfeet.gui import run_gui

        print(SHORT_CREDIT)
        if not settings.lc0_ready:
            print(
                f"Note: lc0 not found at {settings.lc0_path}\n"
                "Hub will open; Play needs lc0. Puzzles/Shop still work.\n"
                "Download: https://lczero.org/play/download/\n"
            )
        else:
            print("Opening Stockfeet hub (Play · Puzzles · Shop · Profile)…")
        # Direct game window if user passed explicit --direct (legacy)
        if getattr(args, "direct", False):
            try:
                settings.require_lc0()
            except FileNotFoundError as exc:
                print(f"Config error: {exc}", file=sys.stderr)
                return 2
            color = args.color
            if color == "random":
                color = random.choice(("white", "black"))
            human_color = chess.WHITE if color == "white" else chess.BLACK
            return run_gui(
                settings,
                human_color=human_color,
                elo=args.elo,
                coach_enabled=not args.no_coach,
                movetime_ms=args.movetime or settings.movetime_ms,
                hub=False,
            )
        return run_gui(settings, hub=True)

    try:
        settings.require_lc0()
    except FileNotFoundError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    color = args.color
    if color == "random":
        color = random.choice(("white", "black"))
    human_color = chess.WHITE if color == "white" else chess.BLACK
    movetime = args.movetime or settings.movetime_ms
    return _cmd_play_cli(settings, args, human_color=human_color, color=color, movetime=movetime)


def _cmd_play_cli(
    settings: Settings,
    args: argparse.Namespace,
    *,
    human_color: chess.Color,
    color: str,
    movetime: int,
) -> int:
    print(about(version=__version__))
    print(SHORT_CREDIT)
    print(f"You play {color}. Commands: UCI move (e2e4), 'resign', 'hint', 'pgn', 'quit'.\n")

    with Lc0Engine(settings.lc0_path, weights=settings.lc0_weights, movetime_ms=movetime) as eng:
        print(f"Engine online: {eng.id_name()}\n")
        coach = Coach(settings, student_elo=args.elo)
        session = GameSession(
            engine=eng,
            coach=coach,
            human_color=human_color,
            coach_after_each_move=False,
        )

        while not session.board.is_game_over():
            if not session.human_to_move:
                print(render_board(session.board, perspective_white=human_color == chess.WHITE))
                print("lc0 thinking...")
                # Play immediately, show board, then optional coach.
                move = eng.play(session.board)
                san = session.board.san(move)
                before = session.board.copy()
                session.board.push(move)
                print(render_board(session.board, perspective_white=human_color == chess.WHITE))
                print(f"\n>>> lc0 ({'White' if human_color == chess.BLACK else 'Black'}) played {san} ({move.uci()})\n")
                if not args.no_coach:
                    analysis = eng.analyse(before, multipv=3)
                    review = classify_move(played=move, before=analysis)
                    print("— Coach —")
                    print(coach.explain_move(review, analysis))
                    print()
                continue

            print(render_board(session.board, perspective_white=human_color == chess.WHITE))
            print(f"FEN: {session.board.fen()}")
            print("Your turn.")
            raw = input("Your move> ").strip().lower()
            if raw in {"q", "quit", "exit"}:
                print("Bye.")
                return 0
            if raw == "resign":
                print("You resigned.")
                break
            if raw == "pgn":
                print(session.to_pgn())
                continue
            if raw == "hint":
                analysis = eng.analyse(session.board, multipv=3)
                if analysis.best:
                    print(
                        f"Hint (lc0): {analysis.best.move.uci()} "
                        f"[{analysis.best.score_text()}]"
                    )
                else:
                    print("No hint available.")
                continue
            try:
                move = _parse_move(session.board, raw)
            except ValueError as exc:
                print(exc)
                continue
            before = session.board.copy()
            san = session.board.san(move)
            session.board.push(move)
            print(f"You played {san} ({move.uci()})")
            if not args.no_coach:
                analysis = eng.analyse(before, multipv=3)
                review = classify_move(played=move, before=analysis)
                print("\n— Coach —")
                print(coach.explain_move(review, analysis))
                print()

        print(render_board(session.board, perspective_white=human_color == chess.WHITE))
        print(_result_text(session.board))
        print("\nPGN:\n")
        print(session.to_pgn())
        print("\n" + coach.lesson_for_elo())
    return 0

def cmd_analyse(settings: Settings, args: argparse.Namespace) -> int:
    movetime = args.movetime or settings.movetime_ms
    board = chess.Board(args.fen)
    with Lc0Engine(settings.lc0_path, weights=settings.lc0_weights, movetime_ms=movetime) as eng:
        print(SHORT_CREDIT)
        print(render_board(board))
        analysis = eng.analyse(board, multipv=3)
        coach = Coach(settings, student_elo=args.elo)
        if analysis.best is None:
            print("No analysis lines returned.")
            return 1
        # Pretend "best move" as reference review for teaching tone.
        review = classify_move(played=analysis.best.move, before=analysis)
        print(coach.explain_move(review, analysis))
        print()
        for i, line in enumerate(analysis.multipv, start=1):
            pv = " ".join(m.uci() for m in line.pv[:8])
            print(f"  {i}. {line.move.uci()} {line.score_text()}  PV: {pv}")
    return 0


def cmd_engine_match(settings: Settings, args: argparse.Namespace) -> int:
    movetime = args.movetime or settings.movetime_ms
    board = chess.Board()
    with Lc0Engine(settings.lc0_path, weights=settings.lc0_weights, movetime_ms=movetime) as eng:
        print(SHORT_CREDIT)
        print(f"Self-play up to {args.plies} plies — {eng.id_name()}")
        for ply in range(args.plies):
            if board.is_game_over():
                break
            move = eng.play(board)
            board.push(move)
            print(f"{ply + 1:02d}. {move.uci()}")
        print(render_board(board))
        print(_result_text(board))
    return 0


def _parse_move(board: chess.Board, raw: str) -> chess.Move:
    raw = raw.replace(" ", "")
    try:
        move = chess.Move.from_uci(raw)
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    try:
        move = board.parse_san(raw)
        return move
    except ValueError as exc:
        raise ValueError(f"Cannot parse move '{raw}'. Use UCI (e2e4) or SAN (Nf3).") from exc


def _result_text(board: chess.Board) -> str:
    if not board.is_game_over():
        return "Game stopped."
    result = board.result(claim_draw=True)
    reason = []
    if board.is_checkmate():
        reason.append("checkmate")
    elif board.is_stalemate():
        reason.append("stalemate")
    elif board.is_insufficient_material():
        reason.append("insufficient material")
    elif board.can_claim_fifty_moves() or board.is_fifty_moves():
        reason.append("fifty-move rule")
    elif board.is_repetition():
        reason.append("repetition")
    detail = f" ({', '.join(reason)})" if reason else ""
    return f"Result: {result}{detail}"


if __name__ == "__main__":
    raise SystemExit(main())
