from __future__ import annotations

from typing import Literal

from hazardly_score import HazardlyScoreBar


def render_hazardly_score_bar(
    score: Literal["A", "B", "C", "D", "E"] | None = None,
    title: str = "Hazardly Score",
) -> str:
    """Compatibility wrapper for older imports."""
    return HazardlyScoreBar(score=score or "A", title=title).to_html()
