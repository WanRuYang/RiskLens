from __future__ import annotations

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
from mlx_engine import (
    run_classifier_agent,
    run_editor_agent,
    run_feedback_agent,
    run_scribe_agent,
    verify_category_vlm,
)
from platform_profiles import MAC_DEV, PIXEL8_ANDROID


URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
INPUT_MODES = {
    "image": "images",
    "url": "product URL",
    "text": "typed text",
}
CLEAR_INPUT = {"text": "", "files": []}


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

    # Screenshots often have legitimate repetitive UI text; we relax the check here
    threshold = 15 if not is_screenshot else 25
    if re.search(r"(.{1,6})\1{" + str(threshold) + r",}", clean):
        return True

    repeated_chunks = re.findall(r"(.{1,4})\1{6,}", clean)
    if repeated_chunks and not is_screenshot:
        return True

    condensed = re.sub(r"\s+", "", clean)
    if len(condensed) >= 80:
        unique_ratio = len(set(condensed)) / max(len(condensed), 1)
        if unique_ratio < 0.15: # Lowered from 0.18 for screenshots
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


def _build_structured_image_ocr_text(raw_text: str, user_notes: str = "") -> tuple[str, str, list[str]]:
    display_lines = _select_display_ocr_lines(raw_text)
    cleaned_passage = _extract_clean_ingredient_text(raw_text) or _build_clean_ocr_passage(display_lines)

    sections: list[tuple[str, str]] = []
    if cleaned_passage:
        sections.append(("Likely Cleaned Read", cleaned_passage))
    if display_lines:
        sections.append(("Detailed OCR Lines", "\n".join(display_lines)))
    else:
        sections.append(("OCR From Images", _dedupe_ocr_text(raw_text)))
    if user_notes.strip():
        sections.append(("User Notes", user_notes.strip()))

    return _join_sections(sections), cleaned_passage, display_lines


def _mode_specific_guidance(mode: str) -> str:
    if mode == "image":
        return "Please upload clearer product, ingredient, or warning images, or switch to a product URL / typed text."
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
    return text, file_paths[:3]


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
    clean = _safe_text(line)
    if not clean:
        return True
    patterns = [
        r"^(?:image|photo|picture)\s*\d*\s*[:：-]?$",
        r"^(?:image|photo|picture)\s*\d*\s*\([^)]*\)\s*[:：-]?$",
        r"^(?:side|front|back|left|right|top|bottom)\s+of\s+(?:box|package|packaging|label)\b.*[:：]?$",
        r"^(?:left|right|front|back)\s+side\b.*[:：]?$",
        r"^ocr\s+from\s+images?$",
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
    if re.search(r"\b(honey\s*stinger|ito\s*en|oi\s*ocha|energy\s+waffle|stroopwafel|waffle|bar|snack|peanut\s+butter|nut\s+butter)\b", clean, re.I):
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
    header = [
        f"Status: {assessment.get('status', 'unknown')}",
        f"Can proceed: {assessment.get('can_proceed', False)}",
    ]
    if assessment.get("reason"):
        header.append(f"Reason: {assessment.get('reason', '')}")
    if assessment.get("recommended_next_step"):
        header.append(f"Recommended next step: {assessment.get('recommended_next_step', '')}")

    body = _join_sections([
        ("Product Name", _url_context_product_name(url_context)),
        ("Listed Category", url_context.get("category", "")),
        ("Processing State", url_context.get("processing_state", "")),
        ("Processing Derivatives", url_context.get("processing_derivatives", "")),
        ("Concentration Analysis", url_context.get("concentration_assessment", "")),
        ("Ingredients / Materials", url_context.get("ingredients_text", "")),
        ("Warnings / Claims", url_context.get("warning_text", "")),
        ("Fetch Error", url_context.get("fetch_error", "")),
    ])
    return "\n".join(header + ([""] if body else []) + ([body] if body else [])).strip()


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
        ocr_text = _sanitize_ocr_content_text(_dedupe_ocr_text(ocr_text))
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
        if _looks_corrupted_ocr(ocr_text, is_screenshot=True):
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
        image_text, _, _ = _build_structured_image_ocr_text(ocr_text, state.direct_text)
        sections.append(("Image OCR", image_text))
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
            f"本地 API 目前無法連線：{detail}\n\n請先在 database 目錄啟動：`python3 -m uvicorn api:app --host 127.0.0.1 --port 8010`",
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
    structured = run_classifier_agent(state.confirmed_text)
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
    final_report = run_editor_agent({**structured, "product_page_url": product_page_url}, api_result)
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

    if state.current_state == "INIT":
        _set_new_turn(state, message_payload)
        ok, intake_text = collect_mode_input(state)
        if not ok:
            return (
                f"I need better {INPUT_MODES.get(state.input_mode, 'input')} before I can continue.\n\n"
                f"Reason: {ok and '' or intake_text}\n\n"
                f"Next step: {_mode_specific_guidance(state.input_mode)}",
                state,
            )

        state.current_state = "AWAITING_TEXT_CONFIRM"
        preview_prefix = ""
        if state.input_mode == "url" and state.url_preview:
            preview_prefix = f"### URL Fetch Preview\n\n{_format_url_preview(state.url_preview)}\n\n---\n\n"
        return (f"{preview_prefix}{_format_first_pass_confirmation(state, intake_text)}", state)

    if state.current_state == "AWAITING_TEXT_CONFIRM":
        if incoming_files or (_first_url(clean_message) and clean_message.lower() not in {"yes", "y", "correct", "ok"}):
            state.current_state = "INIT"
            return process_chat(message_payload, history, state, state.user_id, state.region, state.queue_for_review, state.review_notes)

        if clean_message.lower() in {"yes", "y", "correct", "ok"}:
            state.confirmed_text = state.raw_ocr_text
            state.user_corrected_text = False
        else:
            state.confirmed_text = clean_message
            state.user_corrected_text = True

        if state.input_mode == "text" and _looks_sparse(state.confirmed_text, threshold=25):
            state.current_state = "INIT"
            return (
                "The typed text is still too incomplete for a grounded answer. Please add more detail, or switch to a product URL or images.",
                state,
            )

        proposed = run_classifier_agent(state.confirmed_text)
        state.proposed_category = proposed
        state.current_state = "AWAITING_CAT_CONFIRM"
        state.latest_vlm_check = "N/A"

        if state.input_mode == "image" and state.image_paths:
            try:
                verified = verify_category_vlm(proposed.get("product_use_category", "unknown"), state.image_paths)
                state.latest_vlm_check = "PASSED ✅" if verified else "CAUTION ⚠️ (visual drift detected)"
            except Exception as exc:  # pragma: no cover
                state.latest_vlm_check = f"UNAVAILABLE ({exc})"

        return (
            "I finished the first-pass category/material alignment.\n\n"
            f"- Category: **{proposed.get('product_use_category', 'unknown')}**\n"
            f"- Material/Form: **{proposed.get('material_or_form', 'unknown')}**\n"
            f"- Priority: **{proposed.get('information_priority', 'material_first')}**\n"
            f"- Self-check: **{state.latest_vlm_check}**\n"
            f"- Reasoning: *{proposed.get('reasoning', 'No reasoning provided')}*\n\n"
            "Reply `yes` if this is acceptable, or type a corrected category.",
            state,
        )

    if state.current_state == "AWAITING_CAT_CONFIRM":
        if incoming_files or (_first_url(clean_message) and clean_message.lower() not in {"yes", "y", "correct", "ok"}):
            state.current_state = "INIT"
            return process_chat(message_payload, history, state, state.user_id, state.region, state.queue_for_review, state.review_notes)

        if clean_message.lower() in {"yes", "y", "correct", "ok"}:
            state.confirmed_category = dict(state.proposed_category)
            state.user_corrected_category = False
        else:
            state.confirmed_category = dict(state.proposed_category)
            state.confirmed_category["product_use_category"] = clean_message or state.proposed_category.get("product_use_category", "unknown")
            state.user_corrected_category = True

        healthy, detail = check_local_api()
        if not healthy:
            return (
                f"The local API is not reachable: {detail}\n\nStart it first with `python3 -m uvicorn api:app --host 127.0.0.1 --port 8010`.",
                state,
            )

        state.api_result = run_grounded_search(state)
        intake_assessment = state.api_result.get("intake_assessment", {})
        if not intake_assessment.get("can_proceed", True):
            state.current_state = "INIT"
            return (
                "The system still thinks the current input is not strong enough for a grounded answer.\n\n"
                f"Reason: {intake_assessment.get('reason', 'input not sufficient')}\n\n"
                f"Recommended next step: {intake_assessment.get('recommended_next_step', 'try another method')}",
                state,
            )

        state.final_report = run_editor_agent(
            {
                **state.confirmed_category,
                "product_page_url": state.product_link,
                "confidence_notes": state.latest_vlm_check,
            },
            state.api_result,
        )
        state.current_state = "FEEDBACK"
        return (
            f"### Final Safety Analysis\n\n{state.final_report}\n\n---\nYou can ask follow-up questions, attach clearer images, or paste a new URL / product description to start a new analysis.",
            state,
        )

    if state.current_state == "FEEDBACK":
        if incoming_files or _first_url(clean_message):
            state.current_state = "INIT"
            return process_chat(message_payload, history, state, state.user_id, state.region, state.queue_for_review, state.review_notes)

        action = "NONE"
        feedback_result: dict[str, Any] = {}

        if clean_message.lower() == "rerun":
            action = "RERUN_SEARCH"
            feedback_result = {"action_payload": {}}
            bot_message = "Understood. I will rerun the grounded search with the current text."
        else:
            feedback_result = run_feedback_agent(clean_message, {"api_result": state.api_result, "report": state.final_report})
            bot_message = feedback_result.get(
                "response",
                "I can help rerun with a different region, ingredient clue, or you can paste a new URL / product description for a new analysis.",
            )
            action = feedback_result.get("action", "NONE")

        if action == "RERUN_SEARCH":
            payload = feedback_result.get("action_payload", {})
            state.region = payload.get("region", state.region) or state.region
            ingredient_override = payload.get("ingredients", state.confirmed_category.get("ingredient_text", ""))
            state.api_result = run_grounded_search(state, ingredient_override=ingredient_override)
            intake_assessment = state.api_result.get("intake_assessment", {})
            if not intake_assessment.get("can_proceed", True):
                state.current_state = "INIT"
                return (
                    f"{bot_message}\n\nThe rerun still needs better input. {intake_assessment.get('reason', '')}\n\n"
                    f"Recommended next step: {intake_assessment.get('recommended_next_step', 'try another method')}",
                    state,
                )
            state.final_report = run_editor_agent(
                {
                    **state.confirmed_category,
                    "ingredient_text": ingredient_override or state.confirmed_category.get("ingredient_text", ""),
                    "product_page_url": state.product_link,
                    "confidence_notes": state.latest_vlm_check,
                },
                state.api_result,
            )
            bot_message += f"\n\n### Updated Safety Analysis\n\n{state.final_report}"
        elif action == "UPDATE_CATEGORY":
            payload = feedback_result.get("action_payload", {})
            new_category = payload.get("category", "unknown")
            state.confirmed_category["product_use_category"] = new_category
            state.user_corrected_category = True
            state.api_result = run_grounded_search(state)
            intake_assessment = state.api_result.get("intake_assessment", {})
            if not intake_assessment.get("can_proceed", True):
                state.current_state = "INIT"
                return (
                    f"{bot_message}\n\nThe updated category still needs better input. {intake_assessment.get('reason', '')}",
                    state,
                )
            state.final_report = run_editor_agent(
                {
                    **state.confirmed_category,
                    "product_page_url": state.product_link,
                    "confidence_notes": state.latest_vlm_check,
                },
                state.api_result,
            )
            bot_message += f"\n\n### Updated Safety Analysis\n\n{state.final_report}"

        return bot_message, state

    return "No runnable state is active. Press Start New Analysis to begin again.", state


def chat_wrapper(message_payload, history, state, user_id, region, queue_for_review, review_notes):
    history = history or []
    normalized_history: list[dict[str, str]] = []
    for item in history:
        if isinstance(item, dict) and "role" in item and "content" in item:
            normalized_history.append(item)
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            user_part, bot_part = item
            normalized_history.append({"role": "user", "content": str(user_part or "")})
            normalized_history.append({"role": "assistant", "content": str(bot_part or "")})
    user_text, user_files = _extract_payload_parts(message_payload)
    bot_msg, updated_state = process_chat(
        message_payload,
        normalized_history,
        state,
        user_id,
        region,
        queue_for_review,
        review_notes,
    )
    normalized_history.append({"role": "user", "content": _format_turn_summary(user_text, user_files)})
    normalized_history.append({"role": "assistant", "content": bot_msg})
    return normalized_history, updated_state, CLEAR_INPUT


with gr.Blocks(title="gemma4good vNext") as demo:
    session_state = gr.State(SessionState())

    gr.Markdown("# gemma4good")
    gr.Markdown(
        "Send a product URL, type a product name/description, or attach up to 3 images such as the product front, ingredients panel, a Prop 65 warning sticker, or phone-camera photos. The app will decide how to process the input behind the scenes."
    )
    gr.Markdown(
        f"Current shell: **{MAC_DEV.name}**. Portable target: **{PIXEL8_ANDROID.name}**. This desktop UI is the macOS development harness; OpenAI remains benchmark-only and is not part of the product path."
    )

    with gr.Accordion("Settings", open=False):
        user_id = gr.Textbox(label="User ID", value="local_demo_user")
        region = gr.Textbox(label="Region", value="California, USA")
        queue_for_review = gr.Checkbox(label="Queue this case for review", value=False)
        review_notes = gr.Textbox(label="Optional review notes", lines=2)

    chatbot = gr.Chatbot(height=560, show_label=False)
    composer = gr.MultimodalTextbox(
        file_count="multiple",
        file_types=[".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif", ".avif"],
        placeholder="Type product text, paste a product URL, or attach up to 3 images…",
        label="",
    )
    reset_btn = gr.Button("Start New Analysis", variant="secondary")

    composer.submit(
        fn=chat_wrapper,
        inputs=[composer, chatbot, session_state, user_id, region, queue_for_review, review_notes],
        outputs=[chatbot, session_state, composer],
    )

    def start_over():
        return [], SessionState(), CLEAR_INPUT

    reset_btn.click(
        fn=start_over,
        outputs=[chatbot, session_state, composer],
    )


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
