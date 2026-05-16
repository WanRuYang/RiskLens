from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any

import gradio as gr

from app_shared import (
    build_envelope,
    call_local_api,
    canonicalize_product_url,
    check_local_api,
    dump_debug_json,
    preview_url,
)
from hazardly_score import _parse_nutrition_facts, render_hazardly_flags_html, render_hazardly_score_html
from mlx_engine import (
    run_classifier_agent,
    run_scope_guard_agent,
    run_scribe_agent,
    verify_category_vlm,
)
from platform_profiles import MAC_DEV, PIXEL8_ANDROID
from scope_guard import (
    OUT_OF_SCOPE,
    REFUSAL_MESSAGE,
    UNCLEAR_MESSAGE,
    UNCLEAR_NEEDS_PRODUCT_LABEL,
    classify_scope_fast,
    normalize_scope_decision,
    validate_input_limits,
)


URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
INPUT_MODES = {
    "image": "images",
    "url": "product URL",
    "text": "typed text",
}
CLEAR_INPUT = {"text": "", "files": []}
CLEAR_SCORE_PANEL = ""
APP_CSS = """
@font-face {
    font-display: swap;
    font-family: "ReferoBase";
    font-style: normal;
    font-weight: 300 900;
    src: url("https://refero.design/static/media/base-variable.7a7678ae49a8b605a15b.woff2") format("woff2");
}
:root {
    --hz-bg: #0f172a;
    --hz-surface: rgba(30, 41, 59, 0.7);
    --hz-surface-2: #1e293b;
    --hz-text: #f8fafc;
    --hz-muted: #94a3b8;
    --hz-soft: rgba(59, 130, 246, 0.1);
    --hz-line: rgba(148, 163, 184, 0.2);
    --hz-strong: #3b82f6; --hz-accent: #facc15;
    --hz-accent: #facc15;
    --hz-accent-soft: rgba(250, 204, 21, 0.15);
    --hz-radius-lg: 32px; --hz-accent: #facc15; --hz-accent-soft: rgba(250, 204, 21, 0.15);
    --hz-radius-md: 24px;
    --hz-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2), 0 2px 4px -2px rgba(0, 0, 0, 0.2);
}
body,
.gradio-container {
    background:
        radial-gradient(circle at 0% 0%, rgba(30, 64, 175, 0.15), transparent 40%),
        radial-gradient(circle at 100% 100%, rgba(30, 58, 138, 0.15), transparent 40%),
        #020617 !important;
    color: var(--hz-text) !important;
    font-family: "ReferoBase", -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif !important;
    font-weight: 500;
    letter-spacing: -0.02em;
}
.gradio-container {
    padding-top: 18px !important;
}
.hazardly-shell {
    max-width: 1060px;
    margin: 0 auto;
    padding: 0 18px 28px;
}
.hazardly-intro h1 {
    margin: 0 0 0.2rem;
    font-size: clamp(34px, 7vw, 66px);
    line-height: 0.94;
    font-weight: 900;
    letter-spacing: -0.06em;
}
.hazardly-intro p {
    max-width: 780px;
    margin-top: 0.35rem;
    margin-bottom: 0.45rem;
    color: var(--hz-accent) !important;
    font-size: 15px;
    line-height: 1.5;
}
.hazardly-shell > .gr-accordion,
.hazardly-shell .gr-accordion {
    border-radius: var(--hz-radius-md) !important;
    border: 1px solid var(--hz-line) !important;
    background: var(--hz-surface) !important;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.75) !important;
    backdrop-filter: blur(18px);
}
.hazardly-chat-panel {
    border-radius: var(--hz-radius-lg) !important;
    overflow: hidden;
    border: 1px solid var(--hz-line) !important;
    background: var(--hz-surface) !important;
    box-shadow: var(--hz-shadow), inset 0 0 0 1px rgba(255, 255, 255, 0.7) !important;
    backdrop-filter: blur(16px);
}
.hazardly-flags-card {
    border: 1px solid var(--hz-line);
    border-radius: 28px;
    background: var(--hz-surface-2);
    box-shadow: var(--hz-shadow), inset 0 0 0 1px rgba(255, 255, 255, 0.72);
    padding: 16px 18px;
    margin: 0 0 12px;
}
.hz-flags-title {
    font-size: 18px;
    font-weight: 900;
    letter-spacing: -0.045em;
}
.hz-empty-flags {
    color: rgba(19, 21, 27, 0.68);
    font-size: 14px;
    margin-top: 10px;
}
.hazardly-result-panel {
    max-height: 280px;
    overflow-y: auto;
    border: 1px solid var(--hz-line);
    border-radius: 28px;
    background: var(--hz-surface-2);
    box-shadow: var(--hz-shadow), inset 0 0 0 1px rgba(255, 255, 255, 0.72);
    padding: 8px 18px;
    margin-bottom: 12px;
    scrollbar-width: thin;
}
.hazardly-feedback {
    border-radius: 24px !important;
}
.hz-ingredient-scroll {
    max-height: 120px;
    overflow-y: auto;
    margin-top: 6px;
    padding: 10px 12px;
    border: 1px solid var(--hz-line);
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.66);
    line-height: 1.45;
    scrollbar-width: thin;
}
.hazardly-chat-panel .wrap {
    max-height: 380px;
}
.hazardly-chat-panel .message,
.hazardly-chat-panel .prose {
    font-family: "ReferoBase", -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif !important;
    letter-spacing: -0.02em;
}
.hazardly-chat-panel .bot,
.hazardly-chat-panel .user {
    border-radius: 24px !important;
}
.hazardly-chat-panel .user {
    background: var(--hz-accent) !important; color: #020617 !important; color: #ffffff !important;
    color: var(--hz-text) !important;
    border: 1px solid var(--hz-line) !important;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.72) !important;
}
.hazardly-chat-panel .user * {
    color: var(--hz-text) !important;
}
.hazardly-actions {
    gap: 8px;
    margin-top: 4px;
    margin-bottom: 6px;
}
.hazardly-actions button,
.hazardly-shell button {
    border-radius: 999px !important;
    font-weight: 650 !important;
    letter-spacing: -0.02em !important;
    box-shadow: none !important;
}
.hazardly-actions button.primary,
.hazardly-shell button.primary {
    background: var(--hz-accent) !important; color: #020617 !important; color: #ffffff !important;
    color: #fff !important;
    border-color: var(--hz-accent) !important; color: #020617 !important;
}
.hazardly-actions button.secondary,
.hazardly-shell button.secondary {
    background: #1e293b !important;
    color: var(--hz-text) !important;
    border-color: transparent !important;
}
.hazardly-actions button:hover,
.hazardly-shell button:hover {
    transform: translateY(-1px);
}
.hazardly-composer {
    border-radius: var(--hz-radius-md) !important;
    border: 1px solid var(--hz-line) !important;
    background: var(--hz-surface) !important;
    box-shadow: var(--hz-shadow), inset 0 0 0 1px rgba(255, 255, 255, 0.7) !important;
    backdrop-filter: blur(18px);
}
.hazardly-composer textarea {
    min-height: 64px !important;
    font-family: "ReferoBase", -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif !important;
    letter-spacing: -0.02em !important;
}
.hazardly-composer textarea::placeholder {
    color: rgba(3, 14, 49, 0.42) !important;
}
.hazardly-disclaimer {
    color: var(--hz-accent) !important;
    font-size: 0.86rem;
    line-height: 1.45;
    margin-top: 10px;
}
@media (max-width: 640px) {
    .hazardly-shell {
        padding: 0 10px 20px;
    }
    .hazardly-chat-panel .wrap {
        max-height: 320px;
    }
}
"""


@dataclass
class SessionState:
    user_id: str = "local_demo_user"
    region: str = "California, USA"
    current_state: str = "INIT"
    input_mode: str = "text"
    raw_ocr_text: str = ""
    confirmed_text: str = ""
    proposed_category: dict[str, Any] = field(default_factory=dict)
    confirmed_category: dict[str, Any] = field(default_factory=dict)
    api_result: dict[str, Any] = field(default_factory=dict)
    final_report: str = ""
    image_paths: list[str] = field(default_factory=list)
    product_link: str = ""
    direct_text: str = ""
    queue_for_review: bool = False
    review_notes: str = ""
    user_corrected_text: bool = False
    user_corrected_category: bool = False
    latest_vlm_check: str = "N/A"
    url_preview: dict[str, Any] = field(default_factory=dict)
    pending_food_label_fields: list[str] = field(default_factory=list)
    information_completeness: dict[str, Any] = field(default_factory=dict)


def _safe_text(value: str | None) -> str:
    return value.strip() if isinstance(value, str) else ""


def _join_sections(sections: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    for label, value in sections:
        clean = _safe_text(value)
        if clean:
            parts.append(f"### {label}\n{clean}")
    return "\n\n".join(parts).strip()


def _looks_sparse(text: str, *, threshold: int = 20) -> bool:
    return len(_safe_text(text)) < threshold


def _looks_corrupted_ocr(text: str, is_screenshot: bool = False) -> bool:
    clean = _safe_text(text)
    if not clean:
        return False

    # Strong repeated chunks are a much better signal for Gemma loops than raw
    # character diversity. Dense ingredient/nutrition panels naturally reuse the
    # same letters many times and should not be rejected for that alone.
    threshold = 15 if not is_screenshot else 25
    if re.search(r"(.{1,6})\1{" + str(threshold) + r",}", clean):
        return True

    repeated_chunks = re.findall(r"(.{1,4})\1{6,}", clean)
    if repeated_chunks and not is_screenshot:
        return True

    return False


def _normalize_ocr_line(line: str) -> str:
    clean = _canonicalize_food_label_line(_safe_text(line))
    clean = re.sub(r"\s+", "", clean)
    clean = clean.replace("（", "(").replace("）", ")").replace("：", ":").replace("，", ",")
    return clean


def _canonicalize_food_label_line(line: str) -> str:
    clean = _safe_text(line)
    if not clean:
        return clean

    replacements = [
        (r"^[肉內习]\s*容物[:：]?", "內容物："),
        (r"^[肉內习]\s*容[:：]?\s*物[:：]?", "內容物："),
        (r"^內容[:：]?\s*物[:：]?", "內容物："),
        (r"^[肉內习]\s*容[:：]?", "內容物："),
        (r"食監", "食鹽"),
        (r"基武", "基改"),
    ]
    for pattern, replacement in replacements:
        clean = re.sub(pattern, replacement, clean)
    return clean


def _collapse_repeated_groups(text: str) -> str:
    clean = _canonicalize_food_label_line(_safe_text(text))
    if not clean:
        return clean
    if not re.search(r"[\u3400-\u9fff]", clean):
        return re.sub(r"([A-Za-z])\1{5,}", r"\1", clean)

    previous = None
    current = clean
    while previous != current:
        previous = current
        current = re.sub(r"(.{2,16}?)\1{1,}", r"\1", current)
    return current


def _dedupe_ocr_text(text: str) -> str:
    lines = [_collapse_repeated_groups(line.strip()) for line in (text or "").splitlines()]
    lines = [line for line in lines if line]

    deduped: list[str] = []
    normalized_seen: set[str] = set()
    for line in lines:
        norm = _normalize_ocr_line(line)
        if len(norm) < 2 or norm in normalized_seen:
            continue
        normalized_seen.add(norm)
        deduped.append(line)

    # Drop short fragments if they are already contained inside a longer line.
    filtered: list[str] = []
    normalized_lines = [_normalize_ocr_line(line) for line in deduped]
    for idx, line in enumerate(deduped):
        norm = normalized_lines[idx]
        contained_elsewhere = False
        for jdx, other_norm in enumerate(normalized_lines):
            if idx == jdx:
                continue
            if len(norm) < len(other_norm) and norm and norm in other_norm:
                contained_elsewhere = True
                break
        if not contained_elsewhere:
            filtered.append(line)

    scored = [(line, _ocr_line_score(line)) for line in filtered]
    strong_exists = any(score >= 4.5 for _, score in scored)

    cleaned: list[str] = []
    for line, score in scored:
        norm = _normalize_ocr_line(line)
        if strong_exists and score < 2.2 and len(norm) <= 18:
            continue
        cleaned.append(line)

    # Keep the display compact when OCR produced many tile fragments.
    if len(cleaned) > 8:
        ranking = sorted(
            ((idx, line, _ocr_line_score(line)) for idx, line in enumerate(cleaned)),
            key=lambda item: (item[2], len(_normalize_ocr_line(item[1]))),
            reverse=True,
        )
        keep_indexes = sorted(idx for idx, _, _ in ranking[:8])
        cleaned = [cleaned[idx] for idx in keep_indexes]

    return "\n".join(cleaned).strip()


def _prepare_ocr_texts(raw_text: str) -> tuple[str, str]:
    """Keep a full transcript for Gemma; use compact text only for quality checks."""
    transcript = _safe_text(raw_text)
    quality_text = _sanitize_ocr_content_text(_dedupe_ocr_text(transcript))
    return transcript, quality_text


def _ocr_line_score(line: str) -> float:
    line = _canonicalize_food_label_line(line)
    norm = _normalize_ocr_line(line)
    if not norm:
        return -1.0

    score = min(len(norm), 40) / 10.0
    if re.search(r"(內容物|內容|成分|食品添加物|ingredients?|warning|警語|防腐劑|甜味劑|粘稠劑)", line, re.I):
        score += 3.0
    if re.match(r"^(內容物|內容|成分)[:：]", line):
        score += 4.0
    if any(ch in line for ch in ["、", ",", "，", "(", ")", "（", "）", ":"]):
        score += 1.2
    if re.match(r"^[0-9A-Za-z]{1,3}\W", norm):
        score -= 1.5
    if len(norm) <= 4:
        score -= 2.0
    if re.search(r"[\u3400-\u9fff]", line):
        score += 0.8
    return score


def _select_display_ocr_lines(text: str, *, max_lines: int = 6) -> list[str]:
    deduped = _dedupe_ocr_text(text)
    lines = [_canonicalize_food_label_line(ln.strip()) for ln in deduped.splitlines() if ln.strip()]
    if not lines:
        return []

    scored = [(idx, line, _ocr_line_score(line)) for idx, line in enumerate(lines)]
    header_lines = [(idx, line, score) for idx, line, score in scored if re.match(r"^(內容物|內容|成分)[:：]", line)]
    strong = [(idx, line, score) for idx, line, score in scored if score >= 3.2]
    if header_lines:
        header_idx = header_lines[0][0]
        neighborhood = [(idx, line, score) for idx, line, score in scored if header_idx <= idx <= header_idx + 3 and score >= 2.4]
        strong = header_lines[:1] + [item for item in neighborhood if item[0] != header_idx] + [item for item in strong if item[0] != header_idx]
    if len(strong) < 2:
        strong = sorted(scored, key=lambda item: (item[2], len(_normalize_ocr_line(item[1]))), reverse=True)[:max_lines]

    keep_indexes = sorted(idx for idx, _, _ in strong[:max_lines])
    return [lines[idx] for idx in keep_indexes]


def _is_ingredient_continuation(line: str) -> bool:
    line = _canonicalize_food_label_line(line)
    if not line:
        return False
    if re.match(r"^(內容物|內容|成分)[:：]", line):
        return True
    if re.search(r"(防腐劑|甜味劑|粘稠劑|黏稠劑|食用紅色|食用黃色|辣椒粉|甘草|蔗糖素|苯甲酸|醋磺内|醋磺內|己二酸|二澱粉|玉米糖膠)", line):
        return True
    return False


def _build_clean_ocr_passage(lines: list[str], *, max_chars: int = 260) -> str:
    if not lines:
        return ""

    lines = [_canonicalize_food_label_line(line) for line in lines]
    start_index = 0
    for idx, line in enumerate(lines):
        if re.match(r"^(內容物|內容|成分)[:：]", line):
            start_index = idx
            break

    candidate_lines = lines[start_index:]
    if any(_ocr_line_score(line) >= 5.0 for line in candidate_lines):
        candidate_lines = [line for line in candidate_lines if _ocr_line_score(line) >= 2.4]

    primary = ""
    continuations: list[str] = []
    for line in candidate_lines:
        clean = line.strip().strip(",，、")
        if not clean:
            continue
        if not primary and re.match(r"^(內容物|內容|成分)[:：]", clean):
            primary = clean
            continue
        if _is_ingredient_continuation(clean):
            continuations.append(clean)

    if not primary and candidate_lines:
        primary = candidate_lines[0].strip().strip(",，、")

    merged_parts: list[str] = []
    if primary:
        merged_parts.append(primary)

    for line in continuations:
        if not merged_parts:
            merged_parts.append(line)
            continue
        candidate = merged_parts[-1]
        separator = "" if candidate.endswith(("、", ",", "，", "(", "（", ":")) else " "
        joined = candidate + separator + line
        if len(joined) <= max_chars:
            merged_parts[-1] = joined
        elif len(merged_parts) < 3:
            merged_parts.append(line)

    return "\n".join(merged_parts[:3]).strip()


def _extract_clean_ingredient_text(text: str) -> str:
    display_lines = _select_display_ocr_lines(text)
    passage = _build_clean_ocr_passage(display_lines)
    if passage:
        return passage
    deduped = _dedupe_ocr_text(text)
    header_match = re.search(r"(?:內容物|內容|成分)[:：]\s*(.+)", deduped)
    if header_match:
        return header_match.group(0).strip()
    return ""


def _extract_english_ingredient_text(text: str) -> str:
    clean = _sanitize_ocr_content_text(text)
    patterns = [
        r"(?is)\bINGREDIENTS?\s*[:：]?\s*(.*?)(?:\n\s*(?:Nutrition\s+Facts|Warnings?|Claims?|Directions?|Product\s+Details)\b|\Z)",
        r"(?is)\bIngredients\s*/\s*Materials\s*[:：]?\s*(.*?)(?:\n\s*(?:Nutrition\s+Facts|Warnings?|Claims?|Directions?|Product\s+Details)\b|\Z)",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean)
        if not match:
            continue
        candidate = re.sub(r"\s+", " ", match.group(1)).strip(" .;:-")
        if len(candidate) >= 20 and re.search(r"[,()]|\b(sugar|flour|oil|milk|wheat|cocoa|salt|lecithin)\b", candidate, re.I):
            return candidate[:1200]
    return ""


def _extract_nutrition_facts_text(text: str) -> str:
    clean = _sanitize_ocr_content_text(text)
    if not clean:
        return ""
    patterns = [
        r"(?is)\b(?:Nutrition\s+Facts|Valeur\s+nutritive)\b\s*(.*?)(?:\n\s*(?:Ingredients?|Warnings?|Claims?|Directions?|Product\s+Details)\b|\Z)",
        r"(?is)(?:Servings?|Serv\.?\s*Size|Calories\s+per\s+serving|Calories)\b(.*?)(?:\n\s*(?:Ingredients?|Warnings?|Claims?|Directions?|Product\s+Details)\b|\Z)",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean)
        if not match:
            continue
        candidate = "Nutrition Facts " + re.sub(r"\s+", " ", match.group(1)).strip(" .;:-")
        terms = [
            r"\bcalories?\b",
            r"\bservings?\b",
            r"\b(?:total\s+)?fat\b|\bfat\s*/\s*lipides\b",
            r"\bsaturated\s+fat\b|\bsatur(?:ated|és?)\b",
            r"\bsodium\b",
            r"\btotal\s+carbohydrates?\b|\bcarbohydrate\s*/\s*glucides\b",
            r"\btotal\s+sugars?\b|\bsugars?\s*/\s*sucres?\b",
            r"\badded\s+sugars?\b",
            r"\bprotein\b|\bprotein\s*/\s*protéines?\b",
        ]
        if sum(1 for term in terms if re.search(term, candidate, re.I)) >= 3:
            return candidate[:1200]
    return ""


def _extract_product_identity_text(text: str) -> str:
    # Product identity often lives on short front-label lines such as "OREO".
    # Do not run the aggressive display deduper here; it can discard exactly the
    # short salient text we need before classification.
    clean = _sanitize_ocr_content_text(text)
    lines = [ln.strip(" .;:-") for ln in clean.splitlines() if ln.strip(" .;:-")]
    selected: list[str] = []
    stop_re = re.compile(r"\b(nutrition\s+facts|ingredients?|servings?|calories|total\s+fat|sodium|total\s+sugars?|protein)\b", re.I)
    for line in lines:
        if stop_re.search(line):
            continue
        if _is_layout_description(line):
            continue
        if 2 <= len(line) <= 90 and (re.search(r"[A-Za-z]", line) or re.search(r"[\u3400-\u9fff]", line)):
            selected.append(line)
        if len(selected) >= 8:
            break
    return "\n".join(selected).strip()


def _build_structured_image_ocr_text(raw_text: str, user_notes: str = "") -> tuple[str, str, list[str]]:
    display_lines = _select_display_ocr_lines(raw_text)
    english_ingredients = _extract_english_ingredient_text(raw_text)
    cleaned_passage = english_ingredients or _extract_clean_ingredient_text(raw_text) or _build_clean_ocr_passage(display_lines)
    nutrition_text = _extract_nutrition_facts_text(raw_text)
    product_text = _extract_product_identity_text(raw_text)
    full_ocr = _sanitize_ocr_content_text(_dedupe_ocr_text(raw_text))

    sections: list[tuple[str, str]] = []
    if product_text:
        sections.append(("Product / Front Label Text", product_text))
    if cleaned_passage:
        sections.append(("Ingredients", cleaned_passage))
    if nutrition_text:
        sections.append(("Nutrition Facts", nutrition_text))
    if display_lines:
        sections.append(("Detailed OCR Lines", "\n".join(display_lines)))
    else:
        sections.append(("OCR From Images", full_ocr))
    if full_ocr and full_ocr not in "\n\n".join(value for _, value in sections):
        sections.append(("Full OCR From Images", full_ocr[:2500]))
    if user_notes.strip():
        sections.append(("User Notes", user_notes.strip()))

    # Keep the structured OCR payload factual only. Prompt instructions belong in
    # the classifier prompt, not inside text that later parsers may treat as label data.
    return _join_sections(sections), cleaned_passage, display_lines


def _mode_specific_guidance(mode: str) -> str:
    if mode == "image":
        return "Please upload clearer product, ingredient, nutrition facts, or warning images, or switch to a product URL / typed text."
    if mode == "url":
        return "Please re-enter the product URL, or paste the product title/description in the same message. Amazon pages often block direct fetches, so product images or typed text may work better."
    return "Please add more product detail, ingredients, or warning text. If that is hard to type, try a product URL or images instead."


def _extract_payload_parts(message_payload: Any) -> tuple[str, list[str]]:
    if isinstance(message_payload, str):
        return _safe_text(message_payload), []
    if not isinstance(message_payload, dict):
        return "", []

    text = _safe_text(message_payload.get("text"))
    raw_files = message_payload.get("files") or []
    file_paths: list[str] = []
    for item in raw_files:
        if isinstance(item, str):
            file_paths.append(item)
        elif isinstance(item, dict):
            path = item.get("path") or item.get("name")
            if path:
                file_paths.append(path)
        elif hasattr(item, "path") and getattr(item, "path"):
            file_paths.append(getattr(item, "path"))
        elif hasattr(item, "name") and getattr(item, "name"):
            file_paths.append(getattr(item, "name"))
    return text, file_paths[:5]


def _first_url(text: str) -> str:
    match = URL_RE.search(text or "")
    if not match:
        return ""
    return canonicalize_product_url(match.group(0).strip(" \n\t\r),.;"))


def _strip_urls(text: str) -> str:
    return URL_RE.sub("", text or "").strip()


def _detect_input_mode(text: str, file_paths: list[str]) -> str:
    if file_paths:
        return "image"
    if _first_url(text):
        return "url"
    return "text"


def _has_useful_direct_text(text: str, *, threshold: int = 20) -> bool:
    clean = _safe_text(text)
    if len(clean) < threshold:
        return False
    return not _looks_sparse(clean, threshold=threshold)


def _is_food_category(structured_data: dict[str, Any], text: str = "") -> bool:
    category_blob = " ".join(
        _safe_text(str(part))
        for part in [
            structured_data.get("product_use_category"),
            structured_data.get("material_or_form"),
            structured_data.get("information_priority"),
            structured_data.get("product_name"),
            text,
        ]
        if part
    ).lower()
    return bool(
        re.search(
            r"\b(food|snack|cookie|biscuit|cracker|chips?|candy|bar|waffle|cereal|beverage|drink|tea|coffee|meat|frozen_food|baked_goods|processed_meat|raw_meat)\b",
            category_blob,
        )
    )


def _has_ingredient_evidence(text: str, structured_data: dict[str, Any] | None = None) -> bool:
    structured_data = structured_data or {}
    ingredient_text = _safe_text(structured_data.get("ingredient_text"))
    if len(ingredient_text) >= 20 and re.search(r"[,，、]|\b(water|sugar|flour|oil|salt|milk|soy|wheat|cocoa|lecithin)\b", ingredient_text, re.I):
        return True
    blob = _safe_text(text)
    
    # Increased flexibility for headers and content
    patterns = [
        r"(?i)###\s+Ingredients\s*/\s*Materials\s+(.{20,})",
        r"(?i)\b(?:ingredients?|ingredient\s*/\s*materials)\s*[:：]?\s*(.{20,})",
        r"(?i)(?:成分|內容物)\s*[:：]?\s*(.{20,})"
    ]
    for pattern in patterns:
        match = re.search(pattern, blob, re.DOTALL)
        if match and re.search(r"[,，、]|\b(water|sugar|flour|oil|salt|milk|soy|wheat|cocoa|lecithin)\b", match.group(1), re.I):
            return True
            
    # Fallback to general search if headers aren't clear but keywords are present
    if len(blob) > 50 and re.search(r"\b(ingredients?|成分|內容物)\b", blob, re.I):
        if re.search(r"[,，、]|\b(water|sugar|flour|oil|salt|milk|soy|wheat|cocoa|lecithin)\b", blob, re.I):
            return True
            
    return False


def _has_nutrition_evidence(text: str, structured_data: dict[str, Any] | None = None) -> bool:
    structured_data = structured_data or {}
    blob = " ".join(
        _safe_text(str(part))
        for part in [
            text,
            structured_data.get("nutrition_text"),
            structured_data.get("nutrition_facts"),
            structured_data.get("serving_size"),
        ]
        if part
    )
    if re.search(r"(?i)(?:###\s+)?(?:nutrition\s+facts|valeur\s+nutritive)\b", blob):
        return True
    nutrition_terms = [
        r"\b(?:nutrition\s+facts|valeur\s+nutritive)\b",
        r"\bcalories?\b",
        r"\bservings?\b",
        r"\bserv(?:ing)?\.?\s*size\b",
        r"\b(?:total\s+)?fat\b|\bfat\s*/\s*lipides\b",
        r"\bsaturated\s+fat\b|\bsatur(?:ated|és?)\b",
        r"\bsodium\b",
        r"\btotal\s+(?:carbohydrate|carbohydrates)\b|\bcarbohydrate\s*/\s*glucides\b",
        r"\btotal\s+sugars?\b|\bsugars?\s*/\s*sucres?\b",
        r"\badded\s+sugars?\b",
        r"\bprotein\b|\bprotein\s*/\s*protéines?\b",
        r"%\s*dv\b",
    ]
    return sum(1 for pattern in nutrition_terms if re.search(pattern, blob, re.I)) >= 3


def _missing_food_label_fields(text: str, structured_data: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not _has_ingredient_evidence(text, structured_data):
        missing.append("ingredients")
    return missing


def _format_food_label_request(missing_fields: list[str], product_name: str = "") -> str:
    fields = " and ".join(missing_fields) if missing_fields else "ingredients"
    product = f" for **{product_name}**" if product_name else ""
    return (
        f"This looks like a food product{product}, but I still need the **{fields}** panel for a more complete Hazardly screening.\n\n"
        "Please upload clear close-up photos of:\n"
        "- the ingredients list\n"
        "- the Nutrition Facts table, if you want optional nutrition notes\n\n"
        "Why: the **Hazardly Score** uses chemical, material, contaminant, and process-related exposure signals. "
        "Nutrition facts are optional and only add nutrition notes; they do not change the A-E Hazardly Score. "
        "If you cannot upload more images, you can paste the ingredient text instead."
    )


def _is_product_name_only_text(text: str) -> bool:
    clean = _safe_text(text)
    if not clean:
        return False
    if _first_url(clean):
        return False
    if re.search(r"(?i)\b(ingredients?|nutrition\s+facts?|serving\s+size|calories|total\s+fat|sodium|warning|contains:|materials?|fabric|composition)\b", clean):
        return False
    if "\n" in clean or len(clean) > 160:
        return False
    return bool(re.search(r"[A-Za-z\u3400-\u9fff]", clean))


def _category_status(structured_data: dict[str, Any], text: str) -> str:
    category = _safe_text(structured_data.get("product_use_category"))
    if category and category != "unknown":
        return "inferred"
    if _is_food_category(structured_data, text):
        return "inferred"
    return "missing"


def _build_information_completeness(state: SessionState, structured_data: dict[str, Any] | None = None) -> dict[str, Any]:
    structured_data = structured_data or state.confirmed_category
    text = state.confirmed_text or state.raw_ocr_text or state.direct_text
    product_name = (
        _safe_text(structured_data.get("product_name"))
        or _url_context_product_name(state.url_preview.get("url_context", {}))
        or (_safe_text(state.direct_text) if _is_product_name_only_text(state.direct_text) else "")
        or _extract_product_name_from_text(text)
    )
    category_status = _category_status(structured_data, text)
    is_food = _is_food_category(structured_data, text)
    ingredient_available = _has_ingredient_evidence(text, structured_data)
    nutrition_available = _has_nutrition_evidence(text, structured_data)
    warning_or_claim_available = bool(
        re.search(r"(?i)\b(warning|claim|caution|prop\s*65|organic|non[-\s]?toxic|paraben[-\s]?free|phthalate[-\s]?free|fragrance|contains)\b", text)
        or _safe_text((state.url_preview.get("url_context", {}) or {}).get("warning_text"))
    )
    missing: list[str] = []
    if not product_name:
        missing.append("product name")
    if category_status == "missing":
        missing.append("product category")
    if not ingredient_available:
        missing.append("ingredient list")
    if is_food and not nutrition_available:
        missing.append("nutrition facts")

    if is_food:
        complete = bool(product_name) and category_status != "missing" and ingredient_available and nutrition_available
    else:
        complete = bool(product_name) and category_status != "missing" and (ingredient_available or warning_or_claim_available)

    status = "complete" if complete else "limited"
    result = {
        "product_name": "available" if product_name else "missing",
        "category": category_status,
        "ingredient_list": "available" if ingredient_available else "missing",
        "nutrition_facts": "available" if nutrition_available else "missing",
        "input_source": INPUT_MODES.get(state.input_mode, state.input_mode or "unknown"),
        "analysis_status": status,
        "missing_fields": missing,
        "is_food": is_food,
        "product_name_value": product_name,
        "warning_or_claim_available": warning_or_claim_available,
    }
    state.information_completeness = result
    return result


def _format_information_completeness_check(completeness: dict[str, Any]) -> str:
    lines = [
        "## Information Completeness Check",
        f"Product name: **{completeness.get('product_name', 'missing')}**",
        f"Category: **{completeness.get('category', 'missing')}**",
        f"Ingredient list: **{completeness.get('ingredient_list', 'missing')}**",
        f"Nutrition facts: **{completeness.get('nutrition_facts', 'missing')}**",
        f"Input source: **{completeness.get('input_source', 'unknown')}**",
        f"Analysis status: **{completeness.get('analysis_status', 'limited')}**",
    ]
    if completeness.get("analysis_status") == "limited":
        missing = completeness.get("missing_fields") or []
        if missing:
            lines.append("")
            lines.append(
                "To make this assessment more accurate, please upload a clear photo of the "
                f"{' and '.join(missing)} label, or paste it as text. Without that, I can only provide a limited screening, not a complete product-specific safety analysis."
            )
    return "\n".join(lines)


def _format_missing_information_request(state: SessionState, completeness: dict[str, Any]) -> str:
    missing = completeness.get("missing_fields") or ["ingredient list", "nutrition facts"]
    product_name = completeness.get("product_name_value") or _guess_product_name(state, state.confirmed_text or state.raw_ocr_text)
    intro = _format_information_completeness_check(completeness)
    if state.input_mode == "text" and _is_product_name_only_text(state.direct_text):
        note = (
            "I only have the product name. Please upload or paste the ingredient list and nutrition facts "
            "so I can provide a more complete and product-specific assessment."
        )
        if completeness.get("is_food"):
            note += (
                "\n\nBased on the product name alone, this may have category-level considerations, "
                "but that is not a product-specific finding."
            )
        return f"{intro}\n\n{note}"

    fields = " and ".join(missing)
    return (
        f"{intro}\n\n"
        f"I need the **{fields}** before I can run a complete analysis"
        f"{f' for **{product_name}**' if product_name else ''}.\n\n"
        "Please upload a clear photo of the ingredient list and nutrition facts label, or paste them as text, "
        "so I can provide a more complete assessment."
    )


def _should_pause_for_missing_information(state: SessionState, completeness: dict[str, Any]) -> bool:
    missing = set(completeness.get("missing_fields") or [])
    if state.input_mode == "text" and _is_product_name_only_text(state.direct_text):
        return True
    if not completeness.get("is_food"):
        return False
    if state.input_mode == "image" and missing.intersection({"ingredient list", "nutrition facts"}):
        return True
    if state.input_mode == "url" and {"ingredient list", "nutrition facts"}.issubset(missing):
        return True
    if state.input_mode == "text" and {"ingredient list", "nutrition facts"}.issubset(missing):
        return True
    return False


def _merge_new_user_evidence(state: SessionState, message_payload: Any) -> None:
    text, file_paths = _extract_payload_parts(message_payload)
    if text:
        state.direct_text = "\n".join(part for part in [state.direct_text, _strip_urls(text)] if _safe_text(part)).strip()
        if _first_url(text):
            state.product_link = _first_url(text)
    for path in file_paths:
        if path and path not in state.image_paths:
            state.image_paths.append(path)
    state.image_paths = state.image_paths[:5]


def _run_analysis_from_state(state: SessionState) -> tuple[str, SessionState]:
    envelope = build_envelope(
        user_id=state.user_id,
        region=state.region,
        product_page_url=state.product_link,
        raw_ocr_text=state.confirmed_text,
        structured_data=state.confirmed_category,
        input_mode=state.input_mode,
        user_corrected_text=state.user_corrected_text,
        user_corrected_category=state.user_corrected_category,
        queue_for_review=state.queue_for_review,
        review_notes=state.review_notes,
    )

    state.api_result = call_local_api(envelope.as_api_payload())

    state.current_state = "COMPLETE"
    state.pending_food_label_fields = []
    state.final_report = _format_consistent_safety_report(state)
    return f"{state.final_report}", state


def _format_consistent_safety_report(state: SessionState) -> str:
    structured = _risk_output_for_display(state)
    summary = structured.get("product_summary") or {}
    is_food = summary.get("is_food", False)

    if is_food:
        return _format_food_report(state, structured)
    else:
        return _format_non_food_report(state, structured)


def _format_food_report(state: SessionState, structured: dict[str, Any]) -> str:
    summary = structured.get("product_summary") or {}
    risks = [risk for risk in structured.get("identified_risks", []) if isinstance(risk, dict)]
    nutrition_flags = _deterministic_nutrition_flags(state.confirmed_text)
    
    product_name = _result_product_name(state)
    category = _result_product_category(state)
    ingredients = _get_display_ingredients(state)
    nutrition = _get_display_nutrition(state)
    
    sections = [
        "## Product Info",
        f"Product: **{product_name or 'Unknown product'}**",
        f"Category: **{category or 'Food'}**",
        "Ingredients:",
        _format_product_info_ingredients(ingredients),
        "",
        "## Potential Chemical Signals",
        _format_chemical_signals_section(risks),
        "",
        _report_nutrition_note(nutrition_flags, nutrition != "Missing", state.confirmed_text),
        "",
        "## Recommendation",
        _report_practical_recommendation(risks, nutrition_flags, ingredients != "Missing", nutrition != "Missing"),
        "",
        "## Caveat",
        "This is a screening result only. It does not confirm the presence or amount of any chemical in this specific product. Product-specific confirmation would require a full ingredient/material disclosure, SDS, supplier data, regulatory notice, or lab testing."
    ]
    return "\n".join(section for section in sections if section is not None).strip()


def _format_non_food_report(state: SessionState, structured: dict[str, Any]) -> str:
    summary = structured.get("product_summary") or {}
    risks = [risk for risk in structured.get("identified_risks", []) if isinstance(risk, dict)]
    
    product_name = _result_product_name(state)
    category = _result_product_category(state)
    ingredients = _get_display_ingredients(state)
    
    use_guidance = summary.get("use_guidance", [])

    sections = [
        "## Product Info",
        "",
        f"Product: **{product_name or 'Unknown product'}**",
        f"Category: **{category or 'Non-food'}**",
        f"Ingredient / material list: {ingredients}",
        "",
        "---",
        "",
        "## Potential Chemical Signals",
        _format_chemical_signals_section(risks),
        "",
        "---",
        "",
        "## Use Guidance",
        "\n".join(f"- {item}" for item in use_guidance) if use_guidance else "No specific use guidance identified for the detected signals.",
        "",
        "---",
        "",
        "## Caveat",
        "This is a screening result only. It does not confirm the presence or amount of any chemical in this specific product. Product-specific confirmation would require a full ingredient/material disclosure, SDS, supplier data, regulatory notice, or lab testing."
    ]
    return "\n".join(section for section in sections if section is not None).strip()


def _get_display_ingredients(state: SessionState) -> str:
    text = state.confirmed_text

    if state.confirmed_category.get("ingredient_text"):
        cleaned = _clean_product_info_ingredient_text(state.confirmed_category.get("ingredient_text"))
        if cleaned:
            return cleaned
    
    # Support Markdown headers and literal text
    patterns = [
        r"(?is)###\s+Ingredients\s*/\s*Materials\n(.*?)(?=\n\n|###|\b(?:Nutrition\s+Facts|Valeur\s+nutritive)\b|\Z)",
        r"(?is)\b(?:ingredients?|ingredient\s*/\s*materials)\s*[:：]\s*(.*?)(?=\n\n|###|\b(?:Nutrition\s+Facts|Valeur\s+nutritive)\b|\Z)",
        r"(?is)(?:成分|內容物)\s*[:：]\s*(.*?)(?=\n\n|###|\b(?:Nutrition\s+Facts|Valeur\s+nutritive)\b|\Z)"
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match and len(match.group(1).strip()) > 5:
            cleaned = _clean_product_info_ingredient_text(match.group(1))
            if cleaned:
                return cleaned
        
    return "Missing"


def _get_display_nutrition(state: SessionState) -> str:
    text = state.confirmed_text
    
    # Find block starting with Nutrition Facts
    match = re.search(r"(?is)(?:###\s+)?nutrition\s+facts.*?(?=\n\n|###|\Z)", text)
    if match and len(match.group(0).strip()) > 20:
        cleaned = _clean_display_field_text(match.group(0))
        if cleaned:
            return cleaned
        
    if state.confirmed_category.get("nutrition_text"):
        cleaned = _clean_display_field_text(state.confirmed_category.get("nutrition_text"))
        if cleaned:
            return cleaned
        
    return "Missing"


def _clean_display_field_text(value: str | None) -> str:
    clean = _safe_text(value)
    if not clean:
        return ""
    clean = re.sub(
        r"(?is)\s*\|\s*(?:PRODUCT|INGREDIENTS?|NUTRITION FACTS|WARNINGS/CLAIMS)\s*:\s*NO READABLE TEXT.*$",
        "",
        clean,
    )
    clean = re.sub(
        r"(?im)^\s*(?:(?:PRODUCT|INGREDIENTS?|NUTRITION FACTS|WARNINGS/CLAIMS)\s*:\s*)+$",
        "",
        clean,
    )
    clean = re.sub(r"(?im)^\s*NO READABLE TEXT\s*$", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip(" |")
    if normalize := clean.lower():
        if normalize in {"product:", "nutrition facts:", "ingredients:", "no readable text"}:
            return ""
    return clean


def _remove_nutrition_facts_text(value: str | None) -> str:
    clean = _safe_text(value)
    if not clean:
        return ""
    strong_stop = re.compile(
        r"(?is)\b(?:nutrition\s+facts|valeur\s+nutritive|amount\s*/?\s*serving|amount\s+per\s+serving|"
        r"%\s*dv|%\s*daily\s+value|daily\s+value)\b"
    )
    clean = strong_stop.split(clean, maxsplit=1)[0]
    kept_lines: list[str] = []
    nutrition_row = re.compile(
        r"(?i)\b(?:calories?|total\s+fat|saturated\s+fat|trans\s+fat|cholesterol|sodium|"
        r"fat\s*/\s*lipides|total\s+carbohydrates?|carbohydrate\s*/\s*glucides|fibre|fiber|"
        r"sugars?\s*/\s*sucres?|protein|calcium|iron|potassium)\b"
    )
    for line in clean.splitlines():
        if nutrition_row.search(line) and re.search(r"\d|%", line):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines).strip()


def _clean_product_info_ingredient_text(value: str | None) -> str:
    clean = _remove_nutrition_facts_text(value)
    clean = _clean_display_field_text(clean)
    clean = re.sub(r"(?i)\b(?:amount\s*/?\s*serving|amount\s+per\s+serving)\b.*$", "", clean).strip(" ,;")
    return clean


def _format_product_info_ingredients(ingredients: str) -> str:
    if ingredients == "Missing":
        return ingredients
    return f"<div class=\"hz-ingredient-scroll\">{html.escape(ingredients)}</div>"


def _format_chemical_signals_section(risks: list[dict[str, Any]]) -> str:
    if not risks:
        return "No major risk warnings were identified from the available ingredient and category information."

    lines = []
    for risk in risks:
        name = _safe_text(risk.get("chemical_name")) or "Risk signal"
        signal_type = _risk_signal_type(risk)
        confidence = _display_confidence(risk)
        why = _safe_text(risk.get("consumer_explanation")) or "Screening signal from available product information."
        meaning = _safe_text(risk.get("meaning")) or why
        
        sources = []
        for src in risk.get("risk_sources") or []:
            if isinstance(src, dict) and src.get("is_listed_or_warned"):
                s_name = _safe_text(src.get("source"))
                s_reason = _safe_text(src.get("risk_reason"))
                if s_name:
                    sources.append(f"  - {s_name}: {s_reason or 'Substance of concern'}")

        lines.extend([
            f"### {name}",
            f"- Why flagged: {why}",
            f"- Type: {signal_type}",
            f"- Confidence: {confidence}",
            f"- Evidence source: {_safe_text(risk.get('evidence_source')) or 'general_info'}",
            f"- Route relevance: {_safe_text(risk.get('route_relevance')) or 'uncertain'}",
            f"- Exposure likelihood: {_safe_text(risk.get('exposure_likelihood')) or 'theoretical'}",
            f"- Risk points: {risk.get('risk_points', 0)}",
            "- Sources:"
        ])
        if sources:
            lines.extend(sources)
        else:
            lines.append("  - (Inferred from category or material clues)")
        
        lines.append(f"- Meaning: {meaning}")
        lines.append("")
        
    return "\n".join(lines).strip()


def _report_nutrition_note(nutrition_flags: list[str], nutrition_available: bool, text: str) -> str:
    if not nutrition_available and not nutrition_flags:
        return None
        
    lines = ["## Optional Nutrition Note"]
    if not nutrition_available:
        lines.append("Nutrition facts were not provided, so nutrition-level assessment is limited.")
    elif not nutrition_flags:
        lines.append("No major added sugar, sodium, saturated fat, or calorie flag was identified from the available Nutrition Facts text.")
    else:
        for flag in nutrition_flags:
            detail = _nutrition_detail(flag, text)
            lines.append(f"- **{flag}**: {detail}")
    return "\n".join(lines)


def _report_practical_recommendation(
    risks: list[dict[str, Any]],
    nutrition_flags: list[str],
    ingredient_available: bool,
    nutrition_available: bool,
) -> str:
    lines = []
    strongest = {_safe_text(risk.get("caution_level") or risk.get("user_recommendation")).lower() for risk in risks}
    if "avoid for sensitive groups" in strongest or "avoid if allergic" in strongest:
        lines.append("Review the matched concern(s), especially for sensitive groups, allergies, pregnancy, children, or frequent use.")
    elif "limit frequent exposure" in strongest:
        lines.append("Occasional use may be reasonable for many consumers, but consider limiting frequent repeated exposure.")
    elif risks:
        lines.append("No major high-confidence concern was identified; use normal product-specific judgment.")
    else:
        lines.append("No major risk warnings were identified from the available information.")

    if nutrition_flags:
        lines.append(f"Nutrition-wise, note: {', '.join(nutrition_flags)}.")
    
    missing = []
    if not ingredient_available:
        missing.append("ingredient list")
    if not nutrition_available:
        missing.append("Nutrition Facts panel")
        
    if missing:
        lines.append(f"Note: A more complete assessment would benefit from the missing {', '.join(missing)}.")
        
    return "\n".join(lines).strip()


def _risk_signal_type(risk: dict[str, Any]) -> str:
    text = " ".join(
        _safe_text(str(risk.get(key)))
        for key in ["identification_method", "detection_basis", "evidence_from_product", "chemical_name"]
        if risk.get(key)
    ).lower()
    if "process" in text or "acrylamide" in text or "pah" in text or "nitrosamine" in text or "glycidyl" in text or "3-mcpd" in text:
        return "Process-derived"
    if "packaging" in text or "material" in text or "bpa" in text or "phthalate" in text or "pfas" in text or "ptfe" in text:
        return "Material-based / Packaging-related"
    if "use" in text:
        return "Use-related"
    if "nutrition" in text or "added sugar" in text or "corn syrup" in text:
        return "Nutrition-related"
    if "ingredient" in text or _safe_text(risk.get("identification_method")) == "listed ingredient":
        return "Ingredient-based"
    return "Unknown / Screening signal"


def _display_confidence(risk: dict[str, Any]) -> str:
    raw = _safe_text(risk.get("confidence_level") or risk.get("confidence")).lower()
    if raw in {"explicit", "confirmed", "high"}:
        return "Confirmed"
    if raw in {"likely", "medium"}:
        return "Likely"
    if raw in {"possible", "low"}:
        return "Possible"
    if raw in {"weak inference", "unknown"}:
        return "Unknown"
    return raw.title() if raw else "Unknown"


def _source_names(risk: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for source in risk.get("risk_sources") or []:
        if isinstance(source, dict) and _safe_text(source.get("source")):
            names.append(_safe_text(source.get("source")))
    return list(dict.fromkeys(names))


def _nutrition_detail(flag: str, text: str) -> str:
    clean = _safe_text(text)
    if flag == "High added sugar":
        match = re.search(r"(?i)(?:includes?\s+)?added\s+sugars?\s*([\d.]+\s*g)?\s*(\d+\s*%)?", clean)
        if match and _safe_text(" ".join(part for part in match.groups() if part)):
            return f"Label clue: added sugars {_safe_text(' '.join(part for part in match.groups() if part))}."
        return "Sugar or added-sugar wording appears in the available ingredient or nutrition text."
    if "saturated" in flag.lower():
        match = re.search(r"(?i)saturated\s+fat\s*([\d.]+\s*g)?\s*(\d+\s*%)?", clean)
        if match and _safe_text(" ".join(part for part in match.groups() if part)):
            return f"Label clue: saturated fat {_safe_text(' '.join(part for part in match.groups() if part))}."
        return "Palm oil, palm kernel, vegetable fats, or saturated-fat wording appears in the available label text."
    if "sodium" in flag.lower():
        match = re.search(r"(?i)sodium\s*([\d.]+\s*mg)?\s*(\d+\s*%)?", clean)
        if match and _safe_text(" ".join(part for part in match.groups() if part)):
            return f"Label clue: sodium {_safe_text(' '.join(part for part in match.groups() if part))}."
        return "Sodium or salt wording appears in the available label text."
    return "Nutrition-related screening flag from available label text."


def _result_product_name(state: SessionState) -> str:
    summary = ((state.api_result.get("structured_risk_output") or {}).get("product_summary") or {})
    url_context = state.api_result.get("url_context") or state.url_preview.get("url_context", {})
    candidates = [
        _safe_text(state.confirmed_category.get("product_name")),
        _safe_text(summary.get("product_name")),
        _safe_text(url_context.get("product_name")),
        _safe_text(url_context.get("product_text")),
        _guess_product_name(state, state.confirmed_text),
    ]
    return next((candidate for candidate in candidates if not _is_invalid_product_name(candidate)), "")


def _result_product_category(state: SessionState) -> str:
    inferred = state.api_result.get("inferred_category") or {}
    summary = ((state.api_result.get("structured_risk_output") or {}).get("product_summary") or {})
    raw_parts = [
        _safe_text(state.confirmed_category.get("product_use_category")),
        _safe_text(inferred.get("product_use_category")),
        _safe_text(inferred.get("material_subcategory")),
        _safe_text(summary.get("product_category")),
    ]
    
    # Split all parts by " / " and then deduplicate the tokens to avoid overlap
    all_tokens = []
    for part in raw_parts:
        if not part or part == "unknown":
            continue
        # Split by slash or semicolon
        tokens = [t.strip() for t in re.split(r"\s*[/;]\s*", part) if t.strip()]
        for token in tokens:
            if token.lower() not in [t.lower() for t in all_tokens]:
                all_tokens.append(token)
                
    return " / ".join(all_tokens) if all_tokens else "unknown"


def _risk_output_for_display(state: SessionState) -> dict[str, Any]:
    structured = state.api_result.get("structured_risk_output") or {}
    try:
        from product_risk_formatter import risk_output_from_api_result

        local_structured = risk_output_from_api_result(
            state.api_result,
            product_name=_result_product_name(state),
            ingredients_text=" ".join(
                part
                for part in [
                    state.confirmed_text,
                    state.api_result.get("ingredients_text", ""),
                    (state.api_result.get("url_context") or {}).get("ingredients_text", ""),
                ]
                if _safe_text(str(part))
            ),
        )
    except Exception:
        return structured
    if len(local_structured.get("identified_risks") or []) > len(structured.get("identified_risks") or []):
        return local_structured
    return structured or local_structured


def _deterministic_screening_signals(state: SessionState) -> list[str]:
    structured = _risk_output_for_display(state)
    risks = [risk for risk in structured.get("identified_risks", []) if isinstance(risk, dict)]
    signals: list[str] = []
    for risk in risks:
        name = _safe_text(risk.get("chemical_name"))
        if not name:
            continue
        method = _safe_text(risk.get("identification_method") or risk.get("detection_basis"))
        evidence = _safe_text(risk.get("evidence_from_product"))
        confidence = _safe_text(risk.get("confidence") or risk.get("confidence_level"))
        parts = [name]
        if method:
            parts.append(method)
        if confidence:
            parts.append(f"confidence: {confidence}")
        if evidence:
            parts.append(f"clue: {evidence}")
        signals.append(" - ".join(parts))
    return list(dict.fromkeys(signals))


def _deterministic_nutrition_flags(text: str) -> list[str]:
    normalized = _safe_text(text).lower()
    facts = _parse_nutrition_facts(text)
    flags: list[str] = []
    if re.search(r"\b(added\s+sugars?|includes?\s+added\s+sugars?|cane\s+sugar|sugar|corn\s+syrup|glucose\s+syrup)\b", normalized):
        flags.append("High added sugar")
    if re.search(r"\b(palm\s+oil|palm\s+kernel|vegetable\s+fats?|coconut\s+oil|butter|cream|saturated\s+fat)\b", normalized):
        flags.append("High saturated fat/oils")
    sodium_dv = facts.get("sodium_dv")
    sodium_mg = facts.get("sodium_mg")
    if (sodium_dv is not None and sodium_dv >= 20) or (sodium_mg is not None and sodium_mg >= 460):
        flags.append("High sodium")
    return flags


def _clean_url_context(url_context: dict[str, Any]) -> dict[str, Any]:
    merged = dict(url_context)
    product_text = _safe_text(merged.get("product_text"))
    product_name = _safe_text(merged.get("product_name"))
    if not product_name and product_text:
        product_name = product_text.split("|", 1)[0].strip()

    # URL cleanup must stay deterministic. A generative cleanup pass can mistake
    # bare URLs for technical protocol text when a retailer blocks scraping.
    if re.fullmatch(r"https?://\S+", product_name, re.I):
        product_name = ""
    if re.fullmatch(r"(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}", product_name, re.I):
        product_name = ""

    merged["product_name"] = product_name
    merged["category"] = _safe_text(merged.get("category"))
    merged["ingredients_text"] = _safe_text(merged.get("ingredients_text")) or _safe_text(merged.get("materials"))
    merged["warning_text"] = _safe_text(merged.get("warning_text")) or _safe_text(merged.get("safety_concerns"))
    retail_noise = re.compile(r"\b(your views|featured products|guest ratings|ratings\s*&\s*reviews|disclaimer)\b", re.I)
    relevant_detail = re.compile(r"\b(water|sodium|sulfate|surfactant|fragrance|methylisothiazolinone|benzisothiazolinone|cotton|polyester|nylon|spandex|caution|product warning)\b", re.I)
    if retail_noise.search(merged["ingredients_text"]) and not relevant_detail.search(merged["ingredients_text"]):
        merged["ingredients_text"] = ""
    if retail_noise.search(merged["warning_text"]) and not relevant_detail.search(merged["warning_text"]):
        merged["warning_text"] = ""
    return merged


def _url_context_product_name(url_context: dict[str, Any]) -> str:
    return _safe_text(url_context.get("product_name")) or _safe_text(url_context.get("product_text"))


def _is_layout_description(line: str) -> bool:
    clean = re.sub(r"^\s*#{1,6}\s*", "", _safe_text(line)).strip()
    if not clean:
        return True
    patterns = [
        r"^(?:image|photo|picture)\s*\d*\s*[:：-]?$",
        r"^(?:image|photo|picture)\s*\d*\s*\([^)]*\)\s*[:：-]?$",
        r"^image\s+\d+\s+ocr\s*[:：-]?$",
        r"^image\s+ocr$",
        r"^image\s+ocr\s+transcript$",
        r"^(?:side|front|back|left|right|top|bottom)\s+of\s+(?:box|package|packaging|label)\b.*[:：]?$",
        r"^(?:left|right|front|back)\s+side\b.*[:：]?$",
        r"^ocr\s+from\s+images?$",
        r"^full\s+ocr\s+from\s+images?$",
        r"^ocr\s+section\s+roles?$",
        r"^product\s*/\s*front\s+label\s+text$",
        r"^likely\s+cleaned\s+read$",
        r"^detailed\s+ocr\s+lines$",
    ]
    return any(re.search(pattern, clean, re.I) for pattern in patterns)


def _is_marketing_or_claim_line(line: str) -> bool:
    clean = _safe_text(line)
    if not clean:
        return False
    claim_patterns = [
        r"\btrusted\s+by\b",
        r"\bpro\s+and\s+college\s+teams\b",
        r"\bnew!?\b",
        r"\busda\s+organic\b",
        r"\bnet\s+wt\b",
        r"\bserving\b",
        r"\bcalories\b",
        r"\bgluten\s+free\b",
        r"\bnon[-\s]?gmo\b",
    ]
    return any(re.search(pattern, clean, re.I) for pattern in claim_patterns)


def _product_name_line_score(line: str) -> float:
    clean = _safe_text(line)
    if not clean or _is_layout_description(clean) or _is_marketing_or_claim_line(clean):
        return -10.0
    if re.match(r"^\s*#{1,6}\s+", clean):
        return -10.0
    if re.fullmatch(r"https?://\S+", clean, re.I):
        return -10.0
    if re.fullmatch(r"(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}", clean, re.I):
        return -10.0
    if re.search(r"(ingredients?|warning|內容物|成分|fetched|ocr from images|user notes)", clean, re.I):
        return -5.0

    score = 0.0
    normalized = re.sub(r"[^A-Za-z0-9 +&'-]+", " ", clean).strip()
    words = re.findall(r"[A-Za-z0-9]+", normalized)
    if 2 <= len(words) <= 8:
        score += 3.0
    if re.search(r"\b(honey\s*stinger|ito\s*en|oi\s*ocha|oreo|christie|energy\s+waffle|stroopwafel|waffle|bar|snack|peanut\s+butter|nut\s+butter)\b", clean, re.I):
        score += 5.0
    if re.search(r"\b(flavor|peanut|butter|chocolate|vanilla|organic|energy|unsweetened|green\s+tea|black\s+tea|tea|coffee|juice)\b", clean, re.I):
        score += 1.5
    if clean.isupper() and 4 <= len(clean) <= 80:
        score += 1.0
    if len(clean) > 90:
        score -= 2.0
    return score


def _extract_product_name_from_text(text: str) -> str:
    clean_lines = [
        raw_line.strip(" .;:，,")
        for raw_line in _sanitize_ocr_content_text(text).splitlines()
        if raw_line.strip(" .;:，,")
    ]
    for idx, line in enumerate(clean_lines):
        if not re.search(r"\b(green\s+tea|black\s+tea|oolong\s+tea|tea|coffee|juice|water)\b", line, re.I):
            continue
        selected: list[str] = []
        for prev in clean_lines[max(0, idx - 3):idx]:
            if _is_marketing_or_claim_line(prev) or _is_layout_description(prev):
                continue
            if re.search(r"\b(fl\s*oz|ml|net\s*wt|calories|barcode)\b", prev, re.I):
                continue
            if re.search(r"[A-Za-z]", prev) and len(prev) <= 40:
                selected.append(prev)
        selected.append(line)
        deduped = list(dict.fromkeys(selected))
        if deduped:
            return " ".join(deduped)

    candidates: list[tuple[float, int, str]] = []
    for idx, raw_line in enumerate(clean_lines):
        clean = raw_line.strip(" .;:，,")
        if not clean:
            continue
        score = _product_name_line_score(clean)
        if score > 0:
            candidates.append((score, -idx, clean))
    if not candidates:
        return ""
    candidates.sort(reverse=True)
    return candidates[0][2]


def _sanitize_ocr_content_text(text: str) -> str:
    lines: list[str] = []
    for raw_line in (text or "").splitlines():
        clean = _safe_text(raw_line)
        if not clean or _is_layout_description(clean):
            continue
        lines.append(clean)
    return "\n".join(lines).strip()


def _append_url_context_sections(sections: list[tuple[str, str]], url_context: dict[str, Any]) -> None:
    product_name = _url_context_product_name(url_context)
    ingredients_or_materials = (
        url_context.get("ingredients_text")
        or url_context.get("materials")
        or ""
    )
    warnings_or_claims = (
        url_context.get("warning_text")
        or url_context.get("safety_concerns")
        or ""
    )
    if warnings_or_claims and "\n" not in warnings_or_claims:
        pieces = [piece.strip() for piece in re.split(r"\s*[;|]\s*", warnings_or_claims) if piece.strip()]
        if len(pieces) > 1:
            warnings_or_claims = "\n".join(f"- {piece}" for piece in pieces[:10])
    sections.extend([
        ("Product Name", product_name),
        ("Listed Category", url_context.get("category", "")),
        ("Processing State", url_context.get("processing_state", "")),
        ("Processing Derivatives", url_context.get("processing_derivatives", "")),
        ("Concentration Analysis", url_context.get("concentration_assessment", "")),
        ("Ingredients / Materials", ingredients_or_materials),
        ("Nutrition Facts", url_context.get("nutrition_text", "")),
        ("Serving Size", url_context.get("serving_size", "")),
        ("Warnings / Claims", warnings_or_claims),
    ])


def _try_preview_url_context(state: SessionState) -> tuple[dict[str, Any], dict[str, Any]]:
    if not state.product_link:
        return {}, {}
    preview = preview_url(state.product_link, state.region)
    state.url_preview = preview
    url_context = _clean_url_context(preview.get("url_context", {}))
    preview["url_context"] = url_context
    return preview, url_context


def _format_turn_summary(text: str, file_paths: list[str]) -> str:
    parts: list[str] = []
    clean = _safe_text(text)
    if clean:
        parts.append(clean)
    if file_paths:
        parts.append(f"[attached {len(file_paths)} image(s)]")
    return "\n".join(parts).strip() or "[empty input]"


def _format_url_preview(preview: dict[str, Any]) -> str:
    url_context = preview.get("url_context", {})
    assessment = preview.get("intake_assessment", {})
    
    header = []
    if assessment.get("status") and assessment.get("status") != "sufficient" and "success" not in assessment.get("status"):
        header.append(f"Status: {assessment.get('status', 'unknown')}")
        
    if assessment.get("reason") and not assessment.get("can_proceed", True):
        header.append(f"Reason: {assessment.get('reason', '')}")

    body = _join_sections([
        ("Product Name", _url_context_product_name(url_context)),
        ("Listed Category", url_context.get("category", "")),
        ("Processing State", url_context.get("processing_state", "")),
        ("Processing Derivatives", url_context.get("processing_derivatives", "")),
        ("Concentration Analysis", url_context.get("concentration_assessment", "")),
        ("Ingredients / Materials", url_context.get("ingredients_text", "")),
        ("Nutrition Facts", url_context.get("nutrition_text", "")),
        ("Serving Size", url_context.get("serving_size", "")),
        ("Warnings / Claims", url_context.get("warning_text", "")),
        ("Product Images", "\n".join(url_context.get("product_images", [])[:5]) if isinstance(url_context.get("product_images"), list) else ""),
        ("Fetch Error", url_context.get("fetch_error", "")),
    ])
    return "\n".join(header + ([""] if header and body else []) + ([body] if body else [])).strip()


def _guess_product_name(state: SessionState, intake_text: str) -> str:
    user_hint = _safe_text(state.direct_text)
    if user_hint and len(user_hint) <= 60 and "\n" not in user_hint:
        return user_hint

    if state.url_preview:
        url_name = _url_context_product_name(state.url_preview.get("url_context", {}))
        if url_name and not _is_layout_description(url_name) and not _is_marketing_or_claim_line(url_name):
            return url_name

    best_candidate = _extract_product_name_from_text(intake_text)
    if best_candidate:
        return best_candidate

    text = re.sub(r"###\s+[^\n]+\n", "\n", intake_text)
    for line in [ln.strip() for ln in text.splitlines()]:
        if not line:
            continue
        if _is_layout_description(line):
            continue
        if _is_marketing_or_claim_line(line):
            continue
        if re.fullmatch(r"https?://\S+", line, re.I):
            continue
        if re.fullmatch(r"(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}", line, re.I):
            continue
        if len(line) <= 60 and not re.search(r"(ingredients?|warning|內容物|成分|fetched|ocr from images|user notes)", line, re.I):
            return line
    return "this product"


def _product_name_is_supported_by_text(product_name: str, text: str) -> bool:
    name_tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]+", _safe_text(product_name))
        if len(token) >= 3 and token.lower() not in {"likely", "product", "food", "mix"}
    ]
    if not name_tokens:
        return False
    identity_text = _extract_product_identity_text(text).lower()
    if identity_text:
        return any(token in identity_text for token in name_tokens)
    normalized_text = _safe_text(text).lower()
    return any(token in normalized_text for token in name_tokens)


def _is_invalid_product_name(product_name: str) -> bool:
    clean = _safe_text(product_name)
    if not clean:
        return True
    if _is_layout_description(clean):
        return True
    if re.match(r"^\s*#{1,6}\s+", clean):
        return True
    if re.fullmatch(
        r"(?:image\s+ocr(?:\s+transcript)?|ocr\s+from\s+images?|full\s+ocr\s+from\s+images?|product\s*/\s*front\s+label\s+text)",
        clean,
        re.I,
    ):
        return True
    return False


def _normalize_product_name_from_evidence(product_name: str, intake_text: str) -> str:
    clean_name = _safe_text(product_name)
    clean_text = _safe_text(intake_text)
    if re.search(r"\boreo\b", clean_text, re.I):
        if re.search(r"\b20\s+packs?\b", clean_text, re.I):
            return "OREO 20 Packs"
        if not clean_name or re.search(r"\b(?:oped|ores|dores)\b", clean_name, re.I):
            return "OREO"
    return clean_name


def _refine_food_structure_from_evidence(structured: dict[str, Any], intake_text: str) -> dict[str, Any]:
    refined = dict(structured)
    combined = " ".join(
        part
        for part in [
            _safe_text(refined.get("product_name")),
            _safe_text(refined.get("ingredient_text")),
            _safe_text(intake_text),
        ]
        if part
    ).lower()
    current_category = _safe_text(refined.get("product_use_category")).lower()
    current_subcategory = _safe_text(refined.get("material_subcategory")).lower()

    baked_identity = re.search(r"\b(oreo|cookies?|biscuits?|crackers?)\b", combined)
    baked_matrix = re.search(r"\b(wheat\s+flour|flour)\b", combined)
    if baked_identity and baked_matrix and current_category in {"", "food", "ingestible_food_matrix"}:
        refined["product_use_category"] = "food"
        if current_subcategory in {"", "unknown", "ingestible_food_matrix"}:
            refined["material_subcategory"] = "baked_goods"
        if not _safe_text(refined.get("processing_method")):
            refined["processing_method"] = "Baked/High-Heat"
        if not _safe_text(refined.get("processing_state")):
            refined["processing_state"] = "Baked/High-Heat"
        if not _safe_text(refined.get("processing_derivatives")):
            refined["processing_derivatives"] = "Acrylamide"
    return refined


def _hydrate_structured_from_intake(structured: dict[str, Any], intake_text: str) -> dict[str, Any]:
    """Prefer explicit OCR evidence over unsupported model guesses."""
    hydrated = dict(structured or {})

    extracted_name = _extract_product_name_from_text(intake_text)
    current_name = _safe_text(hydrated.get("product_name"))
    if extracted_name and (
        not current_name
        or _is_invalid_product_name(current_name)
        or not _product_name_is_supported_by_text(current_name, intake_text)
    ):
        hydrated["product_name"] = extracted_name
    hydrated["product_name"] = _normalize_product_name_from_evidence(
        _safe_text(hydrated.get("product_name")),
        intake_text,
    )

    extracted_ingredients = _extract_english_ingredient_text(intake_text) or _extract_clean_ingredient_text(intake_text)
    if extracted_ingredients:
        current_ingredients = _safe_text(hydrated.get("ingredient_text"))
        if len(extracted_ingredients) > len(current_ingredients) or not _has_ingredient_evidence(current_ingredients):
            hydrated["ingredient_text"] = extracted_ingredients

    extracted_nutrition = _extract_nutrition_facts_text(intake_text)
    if extracted_nutrition:
        current_nutrition = _safe_text(hydrated.get("nutrition_text"))
        if len(extracted_nutrition) > len(current_nutrition) or not _has_nutrition_evidence(current_nutrition):
            hydrated["nutrition_text"] = extracted_nutrition

    return _refine_food_structure_from_evidence(hydrated, intake_text)


def _extract_contains_snippet(intake_text: str) -> str:
    clean_text = _sanitize_ocr_content_text(intake_text)
    compact = " ".join(_safe_text(_canonicalize_food_label_line(_dedupe_ocr_text(clean_text))).split())
    patterns = [
        r"(?:內容物|內容|成分)[:：]\s*([^#\n]{1,180})",
        r"(?:ingredients?|ingredients from page)[:：]?\s*([^#\n]{1,180})",
        r"(?:ingredients\s*/\s*materials|materials?|fabric content|composition)[:：]?\s*([^#\n]{1,180})",
    ]
    for pattern in patterns:
        match = re.search(pattern, compact, re.I)
        if match:
            snippet = match.group(1).strip(" .;，,")
            if _is_layout_description(snippet):
                continue
            if _is_marketing_or_claim_line(snippet):
                continue
            return snippet[:180]
    return ""


def _format_first_pass_confirmation(state: SessionState, intake_text: str) -> str:
    product_name = _guess_product_name(state, intake_text)
    contains = "" if _looks_corrupted_ocr(intake_text) else _extract_contains_snippet(intake_text)
    cleaned_match = re.search(r"### Likely Cleaned Read\n(.*?)(?:\n### |\Z)", intake_text, re.S)
    cleaned_passage = _canonicalize_food_label_line(_safe_text(cleaned_match.group(1))) if cleaned_match else ""
    if not contains:
        contains = cleaned_passage
    if _is_layout_description(contains) or _is_marketing_or_claim_line(contains):
        contains = ""
    if normalize := _safe_text(product_name).lower():
        if _safe_text(contains).lower() == normalize:
            contains = ""
    lines = [f"This looks like **{product_name}**."]
    if contains:
        lines.append(f"It seems to contain: **{contains}**.")
    lines.append("")
    lines.append("Reply `yes` if this looks right, or paste corrected text.")
    return "\n".join(lines)


def build_search_envelope(state: SessionState, *, ingredient_override: str = ""):
    structured = dict(state.confirmed_category)
    if ingredient_override:
        structured["ingredient_text"] = ingredient_override
    if not _safe_text(structured.get("ingredient_text")) and state.input_mode == "image":
        fallback_ingredient_text = _extract_clean_ingredient_text(state.confirmed_text or state.raw_ocr_text)
        if fallback_ingredient_text:
            structured["ingredient_text"] = fallback_ingredient_text
    structured.setdefault("category_clues", structured.get("reasoning", ""))
    structured.setdefault("confidence_notes", state.latest_vlm_check)
    return build_envelope(
        user_id=state.user_id,
        region=state.region,
        product_page_url=state.product_link,
        raw_ocr_text=state.confirmed_text or state.raw_ocr_text,
        structured_data=structured,
        input_mode=state.input_mode,
        user_corrected_text=state.user_corrected_text,
        user_corrected_category=state.user_corrected_category,
        queue_for_review=state.queue_for_review or state.user_corrected_text or state.user_corrected_category,
        review_notes=state.review_notes,
    )


def run_grounded_search(state: SessionState, *, ingredient_override: str = "") -> dict[str, Any]:
    envelope = build_search_envelope(state, ingredient_override=ingredient_override)
    return call_local_api(envelope.as_api_payload())


def collect_mode_input(state: SessionState) -> tuple[bool, str]:
    sections: list[tuple[str, str]] = []

    if state.input_mode == "image":
        if not state.image_paths:
            return False, "I still need at least one readable product image."
        url_context: dict[str, Any] = {}
        if state.product_link:
            try:
                _, url_context = _try_preview_url_context(state)
                if url_context:
                    sections.append(("Product Page URL", state.product_link))
                    _append_url_context_sections(sections, url_context)
            except Exception as exc:
                state.latest_feedback = f"URL preview failed while processing image input: {exc}"

        try:
            ocr_text = run_scribe_agent(state.image_paths)
        except Exception as exc:
            state.latest_feedback = str(exc)
            if sections or _has_useful_direct_text(state.direct_text):
                if state.direct_text:
                    sections.append(("User Notes", state.direct_text))
                state.raw_ocr_text = _join_sections(sections)
                return True, state.raw_ocr_text
            return (
                False,
                "I could not finish reading the uploaded image(s). "
                "Please try a clearer photo with the product front, ingredients, or warning label visible. "
                "You can also paste a product URL or type the product name and label text instead.",
            )
        raw_ocr_transcript, ocr_text = _prepare_ocr_texts(ocr_text)
        if _looks_sparse(ocr_text, threshold=15):
            if sections or _has_useful_direct_text(state.direct_text):
                if state.direct_text:
                    sections.append(("User Notes", state.direct_text))
                state.raw_ocr_text = _join_sections(sections)
                return True, state.raw_ocr_text
            return (
                False, 
                "I could not read enough text from the uploaded images. "
                "The image might be too blurry or doesn't contain a clear list of ingredients. "
                "Please try a high-resolution close-up of the ingredient or warning panel."
            )
        has_label_evidence = _has_ingredient_evidence(ocr_text) or _has_nutrition_evidence(ocr_text)
        if _looks_corrupted_ocr(ocr_text, is_screenshot=True) and not has_label_evidence:
            if sections or _has_useful_direct_text(state.direct_text):
                if state.direct_text:
                    sections.append(("User Notes", state.direct_text))
                state.raw_ocr_text = _join_sections(sections)
                return True, state.raw_ocr_text
            return (
                False,
                "The OCR read looks corrupted or repetitive (Gemma loop). "
                "This usually happens when the image resolution is too low or the lighting is poor. "
                "Try a clearer photo or paste the product text directly."
            )
        # Preserve the literal OCR transcript from every image. Gemma performs
        # the second-stage field separation after it has seen all image text.
        sections.append(("Image OCR Transcript", raw_ocr_transcript))
        if state.direct_text:
            sections.append(("User Notes", state.direct_text))
        state.raw_ocr_text = _join_sections(sections)
        return True, state.raw_ocr_text

    if state.input_mode == "url":
        if not state.product_link:
            return False, "I need a product page URL to continue."
        try:
            preview, url_context = _try_preview_url_context(state)
        except Exception as exc:
            state.latest_feedback = str(exc)
            return (
                False,
                f"I could not fetch enough product information from that URL.\n\nError Detail: {exc}\n\n"
                "Please re-enter the link, or try uploading product images or typing the product details instead.",
            )
        
        assessment = preview.get("intake_assessment", {})
        if not assessment.get("can_proceed", True):
            if _has_useful_direct_text(state.direct_text):
                sections.extend([
                    ("Product Page URL", state.product_link),
                    ("Typed Product Context", state.direct_text),
                ])
                _append_url_context_sections(sections, url_context)
                state.raw_ocr_text = _join_sections(sections)
                return True, state.raw_ocr_text
            return False, assessment.get("reason", "I could not read enough from the product page.")
        
        # Simplified sections as requested by user
        _append_url_context_sections(sections, url_context)
        if state.direct_text:
            sections.append(("User Notes", state.direct_text))
        state.raw_ocr_text = _join_sections(sections)
        return True, state.raw_ocr_text

    if not state.direct_text:
        return False, "I need more text about the product to continue."
    if _looks_sparse(state.direct_text, threshold=25):
        return False, "The typed text is still too short to analyze reliably."
    sections.append(("Direct Text Input", state.direct_text))
    state.raw_ocr_text = _join_sections(sections)
    return True, state.raw_ocr_text


def analyze_product(
    images: list[str],
    user_id: str,
    region_label: str,
    product_page_url: str,
    direct_text: str = "",
    queue_for_review: bool = False,
    review_notes: str = "",
    input_mode: str = "image",
) -> tuple[str, str]:
    healthy, detail = check_local_api()
    if not healthy:
        return (
            f"本地 API 目前無法連線：{detail}\n\n請先在 repo 的 database 目錄啟動：`cd /Users/adelie/Projects/gemma4good/database && ../.venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8010`",
            "{}",
        )

    state = SessionState(
        user_id=user_id or "local_demo_user",
        region=region_label or "California, USA",
        input_mode=input_mode,
        image_paths=[path for path in images[:3] if path],
        product_link=canonicalize_product_url(_safe_text(product_page_url)),
        direct_text=_safe_text(direct_text),
        queue_for_review=queue_for_review,
        review_notes=review_notes,
    )
    ok, intake_text = collect_mode_input(state)
    if not ok:
        return f"Input needs improvement: {intake_text}\n\n{_mode_specific_guidance(state.input_mode)}", "{}"

    state.confirmed_text = intake_text
    structured = _hydrate_structured_from_intake(run_classifier_agent(state.confirmed_text), state.confirmed_text)
    if state.input_mode == "image" and _is_food_category(structured, state.confirmed_text):
        missing_fields = _missing_food_label_fields(state.confirmed_text, structured)
        if missing_fields:
            return _format_food_label_request(missing_fields, _safe_text(structured.get("product_name"))), "{}"
    if state.image_paths:
        try:
            vlm_check = (
                "PASSED ✅"
                if verify_category_vlm(structured.get("product_use_category", "unknown"), state.image_paths)
                else "CAUTION ⚠️ (visual drift detected)"
            )
        except Exception as exc:  # pragma: no cover
            vlm_check = f"UNAVAILABLE ({exc})"
    else:
        vlm_check = "N/A"

    structured["confidence_notes"] = vlm_check
    envelope = build_envelope(
        user_id=state.user_id,
        region=state.region,
        product_page_url=state.product_link,
        raw_ocr_text=state.confirmed_text,
        structured_data=structured,
        input_mode=state.input_mode,
        user_corrected_text=bool(state.direct_text and state.image_paths),
        user_corrected_category=False,
        queue_for_review=queue_for_review,
        review_notes=review_notes,
    )
    api_result = call_local_api(envelope.as_api_payload())
    intake_assessment = api_result.get("intake_assessment", {})
    if not intake_assessment.get("can_proceed", True):
        return (
            f"Input needs improvement: {intake_assessment.get('reason', 'The current input was not sufficient.')}\n\n"
            f"Recommended next step: {intake_assessment.get('recommended_next_step', 'try another input method')}",
            dump_debug_json(
                envelope=envelope,
                structured_data=structured,
                api_result=api_result,
                provider="gemma_product",
                raw_ocr_text=state.confirmed_text,
            ),
        )
    state.confirmed_category = structured
    state.api_result = api_result
    final_report = _format_consistent_safety_report(state)
    debug_json = dump_debug_json(
        envelope=envelope,
        structured_data=structured,
        api_result=api_result,
        provider="gemma_product",
        raw_ocr_text=state.confirmed_text,
    )
    return final_report, debug_json


def _set_new_turn(state: SessionState, message_payload: Any) -> tuple[str, list[str]]:
    text, file_paths = _extract_payload_parts(message_payload)
    detected_mode = _detect_input_mode(text, file_paths)
    first_url = _first_url(text)
    state.input_mode = detected_mode
    state.image_paths = file_paths
    state.product_link = first_url
    state.direct_text = _strip_urls(text) if first_url else _safe_text(text)
    state.raw_ocr_text = ""
    state.confirmed_text = ""
    state.proposed_category = {}
    state.confirmed_category = {}
    state.api_result = {}
    state.final_report = ""
    state.latest_vlm_check = "N/A"
    state.url_preview = {}
    state.pending_food_label_fields = []
    state.user_corrected_text = False
    state.user_corrected_category = False
    return text, file_paths


def process_chat(
    message_payload: Any,
    history: list[tuple[str, str]],
    state: SessionState | None,
    user_id_val: str,
    region_val: str,
    queue_for_review_val: bool,
    review_notes_val: str,
):
    if state is None:
        state = SessionState()

    state.user_id = _safe_text(user_id_val) or state.user_id
    state.region = _safe_text(region_val) or state.region
    state.queue_for_review = bool(queue_for_review_val)
    state.review_notes = _safe_text(review_notes_val)

    incoming_text, incoming_files = _extract_payload_parts(message_payload)
    clean_message = _safe_text(incoming_text)

    limit_error = validate_input_limits(clean_message, incoming_files)
    if limit_error:
        return limit_error, SessionState()

    if state.current_state == "INIT":
        _set_new_turn(state, message_payload)
        early_scope = classify_scope_fast(
            state.direct_text or clean_message,
            has_images=bool(state.image_paths),
            has_url=bool(state.product_link),
        )
        if early_scope == OUT_OF_SCOPE:
            return REFUSAL_MESSAGE, SessionState()

        ok, intake_text = collect_mode_input(state)
        if not ok:
            if state.input_mode == "text" and clean_message:
                scope_decision = early_scope or normalize_scope_decision(run_scope_guard_agent(clean_message))
                if scope_decision == OUT_OF_SCOPE:
                    return REFUSAL_MESSAGE, SessionState()
                if scope_decision == UNCLEAR_NEEDS_PRODUCT_LABEL:
                    return UNCLEAR_MESSAGE, SessionState()
            return (
                f"I need better {INPUT_MODES.get(state.input_mode, 'input')} before I can continue.\n\n"
                f"Reason: {intake_text}\n\n"
                f"Next step: {_mode_specific_guidance(state.input_mode)}",
                state,
            )

        fast_scope = classify_scope_fast(
            intake_text,
            has_images=bool(state.image_paths),
            has_url=bool(state.product_link),
        )
        scope_decision = fast_scope or normalize_scope_decision(run_scope_guard_agent(intake_text))
        if scope_decision == OUT_OF_SCOPE:
            return REFUSAL_MESSAGE, SessionState()
        if scope_decision == UNCLEAR_NEEDS_PRODUCT_LABEL:
            return UNCLEAR_MESSAGE, SessionState()

        # Unified v26.6: Run classification and analysis IMMEDIATELY
        state.confirmed_text = intake_text
        proposed = _hydrate_structured_from_intake(run_classifier_agent(state.confirmed_text), state.confirmed_text)
        state.confirmed_category = proposed
        state.latest_vlm_check = "N/A"

        if state.input_mode == "image" and state.image_paths:
            try:
                verified = verify_category_vlm(proposed.get("product_use_category", "unknown"), state.image_paths)
                state.latest_vlm_check = "PASSED ✅" if verified else "CAUTION ⚠️ (visual drift detected)"
            except: pass

        if state.input_mode == "image" and _is_food_category(proposed, state.confirmed_text):
            missing_fields = _missing_food_label_fields(state.confirmed_text, proposed)
            if missing_fields:
                state.current_state = "AWAITING_FOOD_LABEL_IMAGES"
                state.pending_food_label_fields = missing_fields
                product_name = _safe_text(proposed.get("product_name")) or _guess_product_name(state, state.confirmed_text)
                return _format_food_label_request(missing_fields, product_name), state

        return _run_analysis_from_state(state)

    return "Please start a new product analysis with an image, URL, or label text.", SessionState()


def chat_wrapper(message_payload, state, user_id, region, queue_for_review, review_notes):
    bot_msg, updated_state = process_chat(
        message_payload,
        [],
        SessionState(),
        user_id,
        region,
        queue_for_review,
        review_notes,
    )
    return (
        bot_msg,
        updated_state,
        CLEAR_INPUT,
        render_hazardly_score_html(updated_state.api_result, updated_state.confirmed_text),
        render_hazardly_flags_html(updated_state.api_result, updated_state.confirmed_text),
        "",
    )


def submit_feedback(state: SessionState | None, feedback_text: str) -> tuple[SessionState, str, str]:
    state = state or SessionState()
    notes = _safe_text(feedback_text)
    if not state.api_result:
        return state, feedback_text, "Analyze a product first, then submit feedback."
    if not notes:
        return state, feedback_text, "Please add a short correction or feedback note before submitting."
    envelope = build_envelope(
        user_id=state.user_id,
        region=state.region,
        product_page_url=state.product_link,
        raw_ocr_text=state.confirmed_text,
        structured_data=state.confirmed_category,
        input_mode=state.input_mode,
        user_corrected_text=state.user_corrected_text,
        user_corrected_category=state.user_corrected_category,
        queue_for_review=True,
        review_notes=notes,
    )
    payload = envelope.as_api_payload()
    payload["save_to_history"] = False
    try:
        feedback_result = call_local_api(payload)
    except Exception as exc:
        return state, feedback_text, f"Could not submit feedback: {exc}"
    review_id = feedback_result.get("review_queue_id")
    feedback_id = feedback_result.get("user_feedback_id")
    suffixes = []
    if feedback_id:
        suffixes.append(f"feedback {feedback_id}")
    if review_id:
        suffixes.append(f"case {review_id}")
    status = f"Feedback submitted for review{f' ({', '.join(suffixes)})' if suffixes else ''}."
    state.queue_for_review = True
    state.review_notes = notes
    return state, "", status


with gr.Blocks(title="Hazardly") as demo:
    session_state = gr.State(SessionState())

    with gr.Column(elem_classes=["hazardly-shell"]):
        gr.Markdown(
            "# Hazardly\n"
            "Analyze one product at a time from a URL, product label text, or uploaded product images. "
            "For food images, include the front label, ingredients, and Nutrition Facts table so Hazardly can show the Hazardly Score plus separate food flags.",
            elem_classes=["hazardly-intro"],
        )
        gr.Markdown(
            f"Current shell: **{MAC_DEV.name}**. Portable target: **{PIXEL8_ANDROID.name}**. OpenAI remains benchmark-only.",
            elem_classes=["hazardly-intro"],
        )

        with gr.Accordion("Settings", open=False):
            user_id = gr.Textbox(label="User ID", value="local_demo_user")
            region = gr.Textbox(label="Region", value="California, USA")
            queue_for_review = gr.Checkbox(label="Queue this case for review", value=False)
            review_notes = gr.Textbox(label="Optional review notes", lines=2)

        hazardly_score_panel = gr.HTML(value="", label="Hazardly Score")
        hazardly_flags_panel = gr.HTML(value="", label="Hazardly Flags")
        result_panel = gr.Markdown(
            value="Upload a product image, paste a URL, or enter label text to begin.",
            elem_classes=["hazardly-result-panel"],
        )
        composer = gr.MultimodalTextbox(
            file_count="multiple",
            file_types=[".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif", ".avif"],
            placeholder="Type product text, paste a product URL, or attach product / ingredients / nutrition images…",
            label="",
            elem_classes=["hazardly-composer"],
        )
        gr.Markdown(
            "If the response looks wrong, briefly tell us what should be corrected, such as the product name, ingredient read, category, or a missing risk signal. "
            "Your note is saved for review and can help improve future database rules.",
            elem_classes=["hazardly-intro"],
        )
        feedback_notes = gr.Textbox(
            label="Feedback / correction notes",
            placeholder="Example: This is Oreo cookies, not cake mix; ingredients include palm oil.",
            lines=2,
            elem_classes=["hazardly-feedback"],
        )
        submit_feedback_btn = gr.Button("Submit feedback", variant="secondary", size="sm")
        feedback_status = gr.Markdown("")
        
        with gr.Row(visible=True, elem_classes=["hazardly-actions"]):
            analyze_btn = gr.Button("Analyze Product", variant="primary", size="sm")
            reset_btn = gr.Button("Start new analysis", variant="secondary", size="sm")
        
        gr.Markdown(
            "**Disclaimer**: Hazardly is for informational screening only and does not provide medical, legal, or regulatory advice. "
            "Actual risk depends on dose, frequency, and individual sensitivity.",
            elem_classes=["hazardly-disclaimer"],
        )

    def start_over():
        return (
            "Upload a product image, paste a URL, or enter label text to begin.",
            SessionState(),
            CLEAR_INPUT,
            CLEAR_SCORE_PANEL,
            "",
            "",
            "",
        )

    composer.submit(
        fn=chat_wrapper,
        inputs=[composer, session_state, user_id, region, queue_for_review, review_notes],
        outputs=[result_panel, session_state, composer, hazardly_score_panel, hazardly_flags_panel, feedback_status],
    )

    analyze_btn.click(
        fn=chat_wrapper,
        inputs=[composer, session_state, user_id, region, queue_for_review, review_notes],
        outputs=[result_panel, session_state, composer, hazardly_score_panel, hazardly_flags_panel, feedback_status],
    )

    submit_feedback_btn.click(
        fn=submit_feedback,
        inputs=[session_state, feedback_notes],
        outputs=[session_state, feedback_notes, feedback_status],
    )

    reset_btn.click(
        fn=start_over,
        outputs=[result_panel, session_state, composer, hazardly_score_panel, hazardly_flags_panel, feedback_notes, feedback_status],
    )


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(), css=APP_CSS)
