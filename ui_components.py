from __future__ import annotations

from typing import Literal

from risklens_score import RiskLensScoreBar


def render_risklens_score_bar(
    score: Literal["A", "B", "C", "D", "E"] | None = None,
    title: str = "RiskLens Score",
) -> str:
    """Compatibility wrapper for older imports."""
    return RiskLensScoreBar(score=score or "A", title=title).to_html()
