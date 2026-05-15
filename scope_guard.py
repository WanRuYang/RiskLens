from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable


IN_SCOPE_PRODUCT_SAFETY = "IN_SCOPE_PRODUCT_SAFETY"
OUT_OF_SCOPE = "OUT_OF_SCOPE"
UNCLEAR_NEEDS_PRODUCT_LABEL = "UNCLEAR_NEEDS_PRODUCT_LABEL"

REFUSAL_MESSAGE = (
    "I can only help analyze product labels, ingredients, nutrition facts, packaging warnings, "
    "or consumer product safety information. Please upload a product image or paste a product label."
)
UNCLEAR_MESSAGE = (
    "Please upload a product image or paste the product label, ingredient list, nutrition facts, "
    "or packaging warning so I can analyze it."
)

MAX_TEXT_INPUT_CHARS = 8000
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_COUNT = 3

_INJECTION_RE = re.compile(
    r"\b("
    r"ignore (all |the )?(previous|prior) instructions|"
    r"pretend you are|"
    r"reveal (your|the) prompt|"
    r"show (your|the) system prompt|"
    r"answer this coding question|"
    r"do not classify this as out of scope|"
    r"override (your|the) rules|"
    r"change your role"
    r")\b",
    flags=re.IGNORECASE,
)
_OFF_TOPIC_RE = re.compile(
    r"\b("
    r"write (me )?(a )?(python|javascript|java|sql|code)|"
    r"debug (my )?code|"
    r"homework|essay|president|election|politics|diagnose|treatment|"
    r"legal advice|adult content|malware|bomb|phishing"
    r")\b",
    flags=re.IGNORECASE,
)
_PRODUCT_SIGNAL_RE = re.compile(
    r"\b("
    r"ingredient[s]?|nutrition facts|serving size|calories|sodium|added sugars?|"
    r"allergen[s]?|contains[: ]|warning[s]?|prop ?65|product|label|packaging|"
    r"food|snack|cookie|biscuits?|chips?|cracker|detergent|cleaner|shampoo|conditioner|"
    r"plastic|pvc|non-?stick|ptfe|pfas|bpa|phthalate"
    r")\b",
    flags=re.IGNORECASE,
)
_LABEL_MARKER_RE = re.compile(
    r"(ingredients?\s*:|nutrition facts|serving size|contains?\s*:|warnings?\s*:|"
    r"keep out of reach|prop\s*65|supplement facts)",
    flags=re.IGNORECASE,
)


def validate_input_limits(text: str, image_paths: Iterable[str]) -> str | None:
    clean_text = text or ""
    if len(clean_text) > MAX_TEXT_INPUT_CHARS:
        return f"Text input is too large. Please keep it under {MAX_TEXT_INPUT_CHARS:,} characters."

    paths = [path for path in image_paths if path]
    if len(paths) > MAX_IMAGE_COUNT:
        return f"Please upload at most {MAX_IMAGE_COUNT} images per analysis."

    oversized = []
    for path in paths:
        try:
            if Path(path).stat().st_size > MAX_IMAGE_BYTES:
                oversized.append(Path(path).name)
        except OSError:
            continue
    if oversized:
        return (
            "One or more images are too large. Please keep each image under "
            f"{MAX_IMAGE_BYTES // (1024 * 1024)} MB: {', '.join(oversized)}."
        )
    return None


def classify_scope_fast(text: str, *, has_images: bool = False, has_url: bool = False) -> str | None:
    clean = (text or "").strip()
    if _INJECTION_RE.search(clean):
        return OUT_OF_SCOPE
    if _OFF_TOPIC_RE.search(clean) and not _LABEL_MARKER_RE.search(clean):
        return OUT_OF_SCOPE
    if has_images or has_url:
        return IN_SCOPE_PRODUCT_SAFETY
    if _LABEL_MARKER_RE.search(clean):
        return IN_SCOPE_PRODUCT_SAFETY
    if _PRODUCT_SIGNAL_RE.search(clean):
        return UNCLEAR_NEEDS_PRODUCT_LABEL
    return None


def normalize_scope_decision(value: str | None) -> str:
    clean = (value or "").strip().upper()
    if clean in {IN_SCOPE_PRODUCT_SAFETY, OUT_OF_SCOPE, UNCLEAR_NEEDS_PRODUCT_LABEL}:
        return clean
    return UNCLEAR_NEEDS_PRODUCT_LABEL
