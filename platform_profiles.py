from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformProfile:
    name: str
    runtime: str
    ui_shell: str
    max_images: int
    local_model_role: str
    retrieval_mode: str
    notes: str


MAC_DEV = PlatformProfile(
    name="mac_dev",
    runtime="Python 3.12 on macOS",
    ui_shell="Gradio desktop harness",
    max_images=3,
    local_model_role="Full Gemma 4 product-path development and benchmark harness",
    retrieval_mode="Local FastAPI + Postgres on the same machine",
    notes="Use this target for OCR tuning, grounded benchmark runs, and agentic UX iteration.",
)

PIXEL8_ANDROID = PlatformProfile(
    name="pixel8_android",
    runtime="Android app on Pixel 8",
    ui_shell="Native Android client using the same normalized payload and retrieval contract",
    max_images=3,
    local_model_role="On-device Gemma-family reasoning constrained to the same Stage 2 contract",
    retrieval_mode="Compact API payloads and responses; local-first UX with optional remote sync",
    notes="Do not depend on desktop-only libraries, filesystem paths, or a Python UI runtime in the product path.",
)


PLATFORM_PROFILES = {
    MAC_DEV.name: MAC_DEV,
    PIXEL8_ANDROID.name: PIXEL8_ANDROID,
}


def describe_profiles() -> str:
    lines = []
    for profile in PLATFORM_PROFILES.values():
        lines.append(
            f"- {profile.name}: runtime={profile.runtime}; ui={profile.ui_shell}; max_images={profile.max_images}; retrieval={profile.retrieval_mode}"
        )
    return "\n".join(lines)
