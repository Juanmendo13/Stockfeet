import random

import chess

from stockfeet.board_view import render_board
from stockfeet.coach.rules import classify_move, elo_band, improvement_plan
from stockfeet.engine import AnalysisLine, PositionAnalysis
from stockfeet.eval_bar import (
    bottom_fill_fraction,
    format_eval,
    white_advantage_fraction,
)
from stockfeet.legal import about
from stockfeet.profile import Profile
from stockfeet.puzzles import load_puzzles, pick_puzzle
from stockfeet.rewards import puzzle_reward
from stockfeet.shop import buy, get_skin
from stockfeet.strength import pick_human_move, strength_for_elo


def test_format_eval():
    assert format_eval(score_cp=27, mate=None) == "+0.27"
    assert format_eval(score_cp=None, mate=-2) == "M-2"


def test_white_advantage_fraction_bounds():
    assert white_advantage_fraction(score_cp=0, mate=None) == 0.5
    assert white_advantage_fraction(score_cp=None, mate=3) > 0.9
    assert white_advantage_fraction(score_cp=None, mate=-3) < 0.1
    assert 0.6 < white_advantage_fraction(score_cp=200, mate=None) < 1.0


def test_bottom_fill_flips_with_perspective():
    assert bottom_fill_fraction(0.7, perspective_white=True) == 0.7
    assert abs(bottom_fill_fraction(0.7, perspective_white=False) - 0.3) < 1e-9


def test_elo_band():
    assert elo_band(900) == "beginner"
    assert elo_band(1500) == "improving"
    assert elo_band(1700) == "club"
    assert elo_band(2600) == "master"


def test_improvement_plan_non_empty():
    assert len(improvement_plan(1200)) >= 3


def test_render_board_has_ranks():
    text = render_board(chess.Board())
    assert "1  " in text
    assert "8  " in text


def test_classify_best_move():
    move = chess.Move.from_uci("e2e4")
    best = AnalysisLine(move=move, score_cp=30, mate=None, pv=[move])
    analysis = PositionAnalysis(
        fen=chess.STARTING_FEN,
        best=best,
        multipv=[best],
        depth=5,
    )
    review = classify_move(played=move, before=analysis)
    assert review.classification == "best"
    assert review.loss_cp == 0


def test_about_mentions_gpl_and_lc0():
    text = about(version="0.1.0")
    assert "GPL" in text
    assert "lczero.org" in text
    assert "Powered by" in text or "POWERED BY" in text
    assert "Stockfish" in text  # disclaimer: not Stockfish


def test_puzzles_load_and_pick():
    puzzles = load_puzzles()
    assert len(puzzles) >= 100
    assert puzzles[0].rating <= puzzles[-1].rating
    assert all(p.id.startswith("lichess-") for p in puzzles[:5])
    p = pick_puzzle(rating=1200, theme="fork")
    if p is None:
        p = pick_puzzle(rating=1200, theme="all")
    assert p is not None
    assert abs(p.rating - 1200) <= 450


def test_puzzle_path_stages():
    from stockfeet.path import PATH_STAGES, apply_path_solve, path_complete, skip_to_stage

    assert len(PATH_STAGES) >= 10
    assert PATH_STAGES[0].rating < PATH_STAGES[-1].rating
    idx, solved, cleared, bonus = apply_path_solve(
        stage_index=0, solved_in_stage=PATH_STAGES[0].needed - 1, perfect=True
    )
    assert cleared and idx == 1 and solved == 0 and bonus > 0
    assert not path_complete(0)
    assert path_complete(len(PATH_STAGES))
    jump, solved2, skipped = skip_to_stage(current_index=1, target_index=4, skipped_ids=[])
    assert jump == 4 and solved2 == 0
    assert PATH_STAGES[1].id in skipped and PATH_STAGES[3].id in skipped


def test_reward_scales_with_streak():
    low = puzzle_reward(
        rating=800, perfect=False, first_try=False, streak_after=1, seconds=60
    )
    high = puzzle_reward(
        rating=800, perfect=True, first_try=True, streak_after=10, seconds=10
    )
    assert high.coins > low.coins


def test_shop_buy_and_equip(tmp_path):
    profile = Profile(coins=500)
    path = tmp_path / "profile.json"
    profile.save(path)
    profile = Profile.load(path)
    skin = get_skin("ocean", "board")
    assert skin is not None
    msg = buy(profile, skin)
    assert "Purchased" in msg
    assert profile.owns_board("ocean")


def test_strength_scales_with_elo():
    weak = strength_for_elo(900)
    strong = strength_for_elo(2200)
    assert weak.softmax_temp_cp > strong.softmax_temp_cp
    assert weak.blunder_chance > strong.blunder_chance
    assert weak.movetime_ms < strong.movetime_ms
    assert weak.target_best_rate < strong.target_best_rate
    assert weak.noise_sigma_cp > strong.noise_sigma_cp
    assert weak.max_loss_cp > strong.max_loss_cp


def test_pick_human_move_prefers_best_at_high_elo():
    board = chess.Board()
    e4 = chess.Move.from_uci("e2e4")
    d4 = chess.Move.from_uci("d2d4")
    a3 = chess.Move.from_uci("a2a3")
    lines = [
        AnalysisLine(move=e4, score_cp=40, mate=None, pv=[e4]),
        AnalysisLine(move=d4, score_cp=35, mate=None, pv=[d4]),
        AnalysisLine(move=a3, score_cp=-50, mate=None, pv=[a3]),
    ]
    analysis = PositionAnalysis(fen=board.fen(), best=lines[0], multipv=lines, depth=5)
    cfg = strength_for_elo(2700)
    picks = [pick_human_move(analysis, board, cfg, rng=random.Random(i)) for i in range(40)]
    assert picks.count(e4) >= 22


def test_strength_beginner_is_coherent():
    """800 Elo must stay human-beginner, not random-move soft."""
    cfg = strength_for_elo(800)
    assert cfg.target_best_rate >= 0.52
    assert cfg.noise_sigma_cp <= 55
    assert cfg.max_loss_cp <= 140
    assert cfg.blunder_chance <= 0.08
    mid = strength_for_elo(1500)
    assert mid.target_best_rate > cfg.target_best_rate
    assert mid.noise_sigma_cp < cfg.noise_sigma_cp
