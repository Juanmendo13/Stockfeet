from __future__ import annotations

from stockfeet.coach.rules import MoveReview, elo_band, improvement_plan
from stockfeet.config import Settings
from stockfeet.engine import PositionAnalysis


class Coach:
    """Teacher layer on top of lc0 analysis. Optional LLM polish via OpenAI API."""

    def __init__(self, settings: Settings, *, student_elo: int = 1200) -> None:
        self.settings = settings
        self.student_elo = student_elo

    def explain_move(self, review: MoveReview, analysis: PositionAnalysis) -> str:
        base = self._rule_based(review, analysis)
        if not self.settings.llm_enabled:
            return base
        try:
            return self._llm_polish(base, review, analysis)
        except Exception as exc:  # noqa: BLE001 — coach must never crash a game
            return f"{base}\n\n(LLM coach unavailable: {exc})"

    def lesson_for_elo(self) -> str:
        band = elo_band(self.student_elo)
        lines = [
            f"Student level: ~{self.student_elo} Elo ({band})",
            "Suggested focus:",
            *[f"  • {item}" for item in improvement_plan(self.student_elo)],
            "",
            "Engine credit: Leela Chess Zero (lc0) — https://lczero.org/",
        ]
        return "\n".join(lines)

    def _rule_based(self, review: MoveReview, analysis: PositionAnalysis) -> str:
        pv = ""
        if analysis.best and analysis.best.pv:
            pv = " ".join(m.uci() for m in analysis.best.pv[:6])
        candidates = ", ".join(
            f"{line.move.uci()} ({line.score_text()})" for line in analysis.multipv[:3]
        )
        band = elo_band(self.student_elo)
        return "\n".join(
            [
                f"[{review.classification.upper()}] {review.summary}",
                f"Tip ({band}): {review.tip}",
                f"lc0 candidates: {candidates or 'n/a'}",
                f"PV: {pv or 'n/a'}",
            ]
        )

    def _llm_polish(self, base: str, review: MoveReview, analysis: PositionAnalysis) -> str:
        from openai import OpenAI

        client = OpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
        )
        prompt = f"""You are a chess coach. Student Elo ≈ {self.student_elo}.
Use the engine facts below; do not invent a different best move.
Keep 4–7 short sentences. Spanish if the student context is Spanish; otherwise English.
Be concrete (threats, plans, tactics). Mention that analysis comes from lc0.

Engine facts:
{base}

FEN: {analysis.fen}
Played: {review.played.uci()}
Classification: {review.classification}
"""
        response = client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "Chess coach. Faithful to lc0 analysis. No hallucinated moves.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )
        text = response.choices[0].message.content
        return (text or base).strip()
