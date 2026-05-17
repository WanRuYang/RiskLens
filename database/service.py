from __future__ import annotations

import json
import os
import re
import codecs
import subprocess
import sys
import tempfile
import smtplib
from email.message import EmailMessage
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
import requests
from psycopg.rows import dict_row

try:
    from app_shared import (
        extract_ingredient_text_from_readable,
        extract_nutrition_text_from_readable,
        extract_serving_size,
    )
except Exception:  # pragma: no cover - optional when service is imported alone
    extract_ingredient_text_from_readable = None  # type: ignore[assignment]
    extract_nutrition_text_from_readable = None  # type: ignore[assignment]
    extract_serving_size = None  # type: ignore[assignment]

GEMMA4GOOD_PROJECT_ROOT = Path("/Users/adelie/Projects/gemma4good")
if GEMMA4GOOD_PROJECT_ROOT.exists() and str(GEMMA4GOOD_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(GEMMA4GOOD_PROJECT_ROOT))

try:
    from product_label_classifier import predict_product_labels_with_linkages
except Exception:  # pragma: no cover - local optional model path
    predict_product_labels_with_linkages = None

try:
    from product_risk_formatter import risk_output_from_api_result
except Exception:  # pragma: no cover - local optional formatter path
    risk_output_from_api_result = None

GENERIC_CHEM_TOKENS = {
    "acid",
    "salts",
    "salt",
    "compound",
    "compounds",
    "phosphate",
    "phosphates",
    "sulfate",
    "sulfates",
    "sulphate",
    "sulphates",
    "chloride",
    "chlorides",
    "nitrate",
    "nitrates",
    "nitrite",
    "nitrites",
    "acetate",
    "acetates",
    "alcohol",
    "alcohols",
    "oxide",
    "oxides",
    "hydroxide",
    "hydroxides",
    "and",
    "their",
}


def normalize_text(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[\s/_-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


AMAZON_ASIN_RE = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:[/?]|$)", re.I)


def normalize_product_page_url(url: str | None) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""

    parsed = urlparse(raw)
    host = parsed.netloc.lower()
    if "amazon." in host:
        asin_match = AMAZON_ASIN_RE.search(parsed.path)
        if asin_match:
            asin = asin_match.group(1).upper()
            amazon_host = "www.amazon.com" if host.endswith("amazon.com") else parsed.netloc
            return f"https://{amazon_host}/dp/{asin}"
        query = parse_qs(parsed.query)
        for key in ("pd_rd_i", "asin", "ASIN"):
            asin = normalize_text((query.get(key) or [""])[0]).upper()
            if re.fullmatch(r"[A-Z0-9]{10}", asin):
                amazon_host = "www.amazon.com" if host.endswith("amazon.com") else parsed.netloc
                return f"https://{amazon_host}/dp/{asin}"
    return raw


def is_amazon_url(url: str | None) -> bool:
    parsed = urlparse((url or "").strip())
    return "amazon." in parsed.netloc.lower()


def amazon_asin_from_url(url: str | None) -> str:
    parsed = urlparse((url or "").strip())
    if "amazon." not in parsed.netloc.lower():
        return ""
    asin_match = AMAZON_ASIN_RE.search(parsed.path)
    if asin_match:
        return asin_match.group(1).upper()
    query = parse_qs(parsed.query)
    for key in ("pd_rd_i", "asin", "ASIN"):
        asin = normalize_text((query.get(key) or [""])[0]).upper()
        if re.fullmatch(r"[A-Z0-9]{10}", asin):
            return asin
    return ""


def amazon_fetch_candidates(url: str | None) -> list[str]:
    normalized = normalize_product_page_url(url)
    asin = amazon_asin_from_url(normalized)
    if not asin:
        return [normalized] if normalized else []
    return [
        f"https://www.amazon.com/dp/{asin}",
        f"https://www.amazon.com/gp/product/{asin}",
        f"https://www.amazon.com/gp/aw/d/{asin}",
    ]


def fetch_url_html(url: str, headers: dict[str, str]) -> str:
    try:
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status()
        return response.text
    except Exception as requests_exc:
        with tempfile.NamedTemporaryFile(suffix=".html") as tmp:
            proc = subprocess.run(
                ["curl", "--http1.1", "-L", url, "-o", tmp.name],
                text=True,
                capture_output=True,
                timeout=25,
            )
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or str(requests_exc)) from requests_exc
            with open(tmp.name, encoding="utf-8", errors="ignore") as handle:
                return handle.read()


def _clean_html_text(value: str | None) -> str:
    text = unescape(unquote(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text, flags=re.I)
    text = re.sub(r"&amp;", "&", text, flags=re.I)
    text = re.sub(r"&quot;", '"', text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \n\t\r-:|")


def _clean_amazon_ingredient_text(value: str | None) -> str:
    text = _clean_html_text(value)
    text = re.sub(r"^(?:Active\s+)?Ingredients?\s*", "", text, flags=re.I).strip(" :.-")
    text = re.sub(r"\.(?=Contains:)", ". ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if re.search(r"\b(function|var|window\.|document\.|placeholder|readystatechange)\b", text, re.I):
        return ""
    return text[:1200]


def infer_retail_category_from_text(text: str | None) -> str:
    normalized = normalize_text(text)
    if re.search(r"\b(conditioner|shampoo|body wash|lotion|serum|moisturizer|deodorant|hair|skin care|beauty)\b", normalized):
        return "Personal Care"
    if re.search(r"\b(detergent|cleaner|disinfect|degreaser|laundry|dish soap)\b", normalized):
        return "Household Cleaner"
    if re.search(r"\b(waffle|bar|protein|coffee|tea|snack|cereal|granola|food|drink|beverage|meat|duck|chicken|beef)\b", normalized):
        return "Food"
    return ""


def _extract_amazon_context(html: str, url: str) -> dict[str, str]:
    title = ""
    bullets: list[str] = []
    ingredients_text = ""
    warning_text = ""

    title_patterns = [
        r'<span[^>]+id=["\']productTitle["\'][^>]*>(.*?)</span>',
        r'<meta[^>]+name=["\']title["\'][^>]+content=["\'](.*?)["\']',
        r'"title"\s*:\s*"([^"]+)"',
        r'<title>(.*?)</title>',
        r'property=["\']og:title["\']\s+content=["\'](.*?)["\']',
    ]
    for pattern in title_patterns:
        match = re.search(pattern, html, re.I | re.S)
        if match:
            title = _clean_html_text(match.group(1))
            if title:
                break

    bullet_sections: list[str] = []
    for section_id in ("pqv-feature-bullets", "featurebullets_feature_div"):
        section_match = re.search(
            rf'<div[^>]+id=["\']{section_id}["\'][^>]*>(.*?)(?:<div[^>]+id=["\']pqv-description["\']|<div[^>]+id=["\']productDescription|<div[^>]+id=["\']importantInformation|</ul>\s*</div>)',
            html,
            re.I | re.S,
        )
        if section_match:
            bullet_sections.append(section_match.group(1))

    for section in bullet_sections:
        for match in re.finditer(r'<li[^>]*>\s*<span[^>]*class=["\']a-list-item["\'][^>]*>(.*?)</span>\s*</li>', section, re.I | re.S):
            cleaned = _clean_html_text(match.group(1))
            if cleaned and cleaned not in bullets and not _is_url_noise_line(cleaned):
                bullets.append(cleaned)
        if bullets:
            break

    if not bullets:
        feature_match = re.search(r'"feature_bullets"\s*:\s*\[(.*?)\]', html, re.I | re.S)
        if feature_match:
            for quoted in re.findall(r'"([^"]{20,240})"', feature_match.group(1)):
                cleaned = _clean_html_text(quoted)
                if cleaned and cleaned not in bullets and not _is_url_noise_line(cleaned) and not re.search(r"\b(var|function|return|placeholder|readystatechange|plugin)\b", cleaned, re.I):
                    bullets.append(cleaned)

    ingredient_patterns = [
        r'<span[^>]*class=["\']a-text-bold["\'][^>]*>\s*Ingredients\s*</span>\s*<p>\s*<p>(.*?)</p>\s*</p>',
        r'<span[^>]*>\s*Ingredients\s*</span>\s*<p>\s*<p>(.*?)</p>\s*</p>',
        r'<span[^>]*class=["\']a-text-bold["\'][^>]*>\s*Ingredients\s*</span>\s*(.*?)(?:<span[^>]*class=["\']a-text-bold["\']|</div>\s*</div>|<h2>|$)',
        r'(?:Important Information|Safety Information).*?(?:Ingredients|Ingredient)\s*(.*?)(?:Directions|Legal Disclaimer|Product Description|About this item|$)',
        r'(?:Materials\s*&\s*Care|Product details).*?(?:Active\s+Ingredients|Ingredients|Ingredient)\s*(.*?)(?:Additional details|Directions|Safety Information|Legal Disclaimer|Product Description|About this item|$)',
        r'(?:Active\s+Ingredients|Ingredients|Ingredient)\s*[:：]?\s*(.*?)(?:\.\s+[A-Z][a-z]+:|Directions|Legal Disclaimer|Additional details|Safety Information|Product Description|About this item|$)',
        r'(?:Product Description|About this item).*?(?:Active\s+Ingredients|Ingredients|Ingredient)\s*[:：]?\s*(.*?)(?:Directions|Legal Disclaimer|$)',
    ]
    for pattern in ingredient_patterns:
        match = re.search(pattern, html, re.I | re.S)
        if match:
            ingredients_text = _clean_amazon_ingredient_text(match.group(1))
            if ingredients_text and len(normalize_text(ingredients_text)) >= 20:
                break

    warning_patterns = [
        r'<h3>\s*Legal Disclaimer\s*</h3>\s*<p>(.*?)</p>',
        r'(Cancer and Reproductive Harm.*?)(?:Directions|Ingredients|Product Description|$)',
        r'(Keep out of reach of children.*?)(?:Directions|Ingredients|Product Description|$)',
    ]
    for pattern in warning_patterns:
        match = re.search(pattern, html, re.I | re.S)
        if match:
            warning_text = _clean_html_text(match.group(1))
            if warning_text:
                break

    cleaned_bullets = _split_claim_lines("\n".join(bullets))
    product_text = title
    claims_text = "\n".join(f"- {line}" for line in cleaned_bullets[:6])
    if warning_text:
        warning_text = _clean_url_field_text(f"{claims_text}\n{warning_text}", field="claims")
    else:
        warning_text = claims_text

    return {
        "product_text": product_text,
        "category": infer_retail_category_from_text(product_text),
        "ingredients_text": ingredients_text,
        "nutrition_text": _extract_nutrition_context(html),
        "warning_text": warning_text,
    }


def _extract_amazon_slug_title(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or ""
    match = re.search(r"/([A-Za-z0-9][A-Za-z0-9\-]{6,})/dp/[A-Z0-9]{10}", path, re.I)
    if not match:
        return ""
    slug = match.group(1)
    slug = re.sub(r"[-_]+", " ", slug)
    slug = re.sub(r"\s+", " ", slug).strip()
    return slug


def _extract_generic_slug_title(url: str) -> str:
    parsed = urlparse(url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        return ""

    best = ""
    for segment in segments:
        candidate = unquote(segment)
        candidate = re.sub(r"\.[a-z0-9]{2,6}$", "", candidate, flags=re.I)
        candidate = re.sub(r"[-_+]+", " ", candidate)
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if len(candidate) > len(best) and re.search(r"[A-Za-z]{3,}", candidate):
            best = candidate
    return best


def _extract_meta_content(html: str, attr_name: str, attr_value: str) -> str:
    patterns = [
        rf'<meta[^>]+{attr_name}=["\']{re.escape(attr_value)}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+content=["\'](.*?)["\'][^>]+{attr_name}=["\']{re.escape(attr_value)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.I | re.S)
        if match:
            text = _clean_html_text(match.group(1))
            if text:
                return text
    return ""


def _extract_json_ld_field(html: str, field_name: str) -> str:
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.I | re.S,
    )
    for script_body in scripts:
        cleaned_body = script_body.strip()
        if not cleaned_body:
            continue
        matches = re.findall(rf'"{re.escape(field_name)}"\s*:\s*"(.*?)"', cleaned_body, re.I | re.S)
        for value in matches:
            text = _clean_html_text(value)
            if text:
                return text
    return ""


def _iter_nested_values(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _iter_nested_values(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_nested_values(item)


def _extract_target_json_context(html: str, url: str) -> dict[str, str]:
    if "target.com" not in urlparse(url).netloc.lower():
        return {"product_text": "", "category": "", "ingredients_text": "", "warning_text": ""}

    best: dict[str, str] = {
        "product_text": "",
        "category": "",
        "ingredients_text": "",
        "nutrition_text": "",
        "warning_text": "",
    }

    for match in re.finditer(r"JSON\.parse\(\"(.*?)\"\)", html, re.S):
        try:
            decoded = codecs.decode(match.group(1), "unicode_escape")
            blob = json.loads(decoded)
        except Exception:
            continue

        for node in _iter_nested_values(blob):
            if not isinstance(node, dict):
                continue

            nutrition = node.get("nutrition_facts")
            if isinstance(nutrition, dict):
                raw_ingredients = re.sub(
                    r"\s*\(Parenthesis State Source of Ingredient\)\.?\s*$",
                    "",
                    nutrition.get("ingredients", ""),
                    flags=re.I,
                )
                ingredients = _clean_url_field_text(raw_ingredients, field="ingredients")
                warning = _clean_url_field_text(nutrition.get("warning", ""), field="claims")
                if ingredients:
                    best["ingredients_text"] = ingredients
                if warning:
                    best["warning_text"] = warning
                if extract_nutrition_text_from_readable is not None:
                    nutrition_text = extract_nutrition_text_from_readable(_clean_html_text(json.dumps(nutrition)))
                    if nutrition_text:
                        best["nutrition_text"] = nutrition_text

            category = node.get("category")
            if isinstance(category, dict) and category.get("name"):
                best["category"] = _clean_html_text(category.get("name"))

            description = node.get("product_description")
            if isinstance(description, dict):
                title = _clean_html_text(description.get("title"))
                if title:
                    best["product_text"] = title
                bullets = description.get("bullet_descriptions")
                if isinstance(bullets, list):
                    bullet_text = "\n".join(_clean_html_text(str(bullet)) for bullet in bullets)
                    claims = _clean_url_field_text(bullet_text, field="claims")
                    if claims:
                        best["warning_text"] = "\n".join(
                            dict.fromkeys(
                                line for line in [best["warning_text"], claims] if normalize_text(line)
                            )
                        )

            if all(best.get(key) for key in ("product_text", "ingredients_text", "warning_text")):
                return best

    return best


MATERIAL_KEYWORDS = (
    "cotton",
    "organic cotton",
    "polyester",
    "recycled polyester",
    "nylon",
    "polyamide",
    "spandex",
    "elastane",
    "wool",
    "merino",
    "cashmere",
    "rayon",
    "viscose",
    "linen",
    "silk",
    "acrylic",
    "modal",
    "lyocell",
    "hemp",
    "leather",
    "faux leather",
    "polyurethane",
)

URL_NOISE_PHRASES = (
    "your views",
    "featured products",
    "guest ratings",
    "guest ratings & reviews",
    "ratings & reviews",
    "disclaimer",
    "general disclaimer",
    "content on this site is for reference purposes only",
    "target does not represent or warrant",
    "we recommend that you do not rely solely",
    "shop all",
    "add to cart",
    "shipping",
    "returns",
)

CLAIM_LABELS = (
    "product warning",
    "product form",
    "formulation",
    "sustainability claims",
    "net weight",
    "number of uses",
    "tcin",
    "upc",
    "item number",
    "origin",
    "caution",
    "contains",
    "first aid treatment",
    "contains fragrance allergens",
)


def _is_url_noise_line(line: str) -> bool:
    normalized = normalize_text(line)
    if not normalized:
        return True
    return any(phrase in normalized for phrase in URL_NOISE_PHRASES)


def _split_claim_lines(text: str | None) -> list[str]:
    raw = _clean_html_text(text)
    if not raw:
        return []

    # Insert breaks before common retail spec labels so the preview can show
    # compact bullets rather than one long scraped paragraph.
    label_pattern = "|".join(re.escape(label) for label in CLAIM_LABELS)
    raw = re.sub(rf"\s+({label_pattern})\s*:", r"\n\1:", raw, flags=re.I)
    raw = re.sub(r"\s+(Non[-\s]Toxic|Paraben[-\s]Free|Phthalate[-\s]Free|Phosphate[-\s]Free|Animal By[-\s]Product[-\s]Free)", r"\n\1", raw, flags=re.I)

    lines: list[str] = []
    for part in re.split(r"[\n;]+", raw):
        clean = part.strip(" .;:-,\t")
        if not clean or _is_url_noise_line(clean):
            continue
        if len(clean) > 180:
            clean = clean[:177].rstrip() + "..."
        if clean not in lines:
            lines.append(clean)
    return lines[:10]


def _clean_url_field_text(text: str | None, *, field: str) -> str:
    raw = _clean_html_text(text)
    if not raw:
        return ""

    if field == "claims":
        return "\n".join(f"- {line}" for line in _split_claim_lines(raw))

    kept: list[str] = []
    for part in re.split(r"[\n|]+", raw):
        clean = part.strip(" .;:-\t")
        if not clean or _is_url_noise_line(clean):
            continue
        if field == "ingredients" and re.fullmatch(r"N/?A|none|not applicable", clean, re.I):
            continue
        kept.append(clean)

    if field == "ingredients":
        relevant = [
            line for line in kept
            if re.search(r"(ingredients?|material|fabric|composition|\d{1,3}%|cotton|polyester|nylon|spandex|liquid|concentrated|detergent)", line, re.I)
        ]
        kept = relevant or []

    compact = " | ".join(dict.fromkeys(kept))
    return compact[:500]


def _extract_material_context(html: str) -> str:
    candidates: list[str] = []

    label_patterns = [
        r"(?:Material|Materials|Fabric|Fabric content|Shell|Body|Lining|Composition|Content)\s*[:：]\s*(.*?)(?:<|Care|Fit|Size|Details|Description|$)",
        r'"(?:material|materials|fabric|composition|content)"\s*:\s*"(.*?)"',
    ]
    for pattern in label_patterns:
        for match in re.finditer(pattern, html, re.I | re.S):
            text = _clean_html_text(match.group(1))
            if text and text not in candidates:
                candidates.append(text)

    percent_patterns = [
        r"(?:\b\d{1,3}%\s*[A-Za-z][A-Za-z \-/]{2,40})(?:,\s*\d{1,3}%\s*[A-Za-z][A-Za-z \-/]{2,40}){0,5}",
        r"(?:\b(?:cotton|polyester|nylon|polyamide|spandex|elastane|wool|rayon|viscose|linen|silk|acrylic|modal|lyocell|hemp|leather|polyurethane)\b.*?\b\d{1,3}%)(?:.*?\b\d{1,3}%\b){0,4}",
    ]
    for pattern in percent_patterns:
        for match in re.finditer(pattern, html, re.I | re.S):
            text = _clean_html_text(match.group(0))
            if text and text not in candidates:
                candidates.append(text)

    keyword_hits = []
    lowered = html.lower()
    for keyword in MATERIAL_KEYWORDS:
        if keyword in lowered:
            keyword_hits.append(keyword)
    if keyword_hits:
        summary = ", ".join(dict.fromkeys(keyword_hits))
        if summary and summary not in candidates:
            candidates.append(summary)

    for candidate in candidates:
        if len(normalize_text(candidate)) >= 10:
            return candidate[:260]
    return ""


def _extract_generic_context(html: str, url: str) -> dict[str, str]:
    target_context = _extract_target_json_context(html, url)
    if target_context.get("product_text") or target_context.get("ingredients_text") or target_context.get("warning_text"):
        return target_context

    title = ""
    desc = ""
    ingredients_text = ""
    warning_text = ""
    category = ""

    title_candidates = [
        _extract_meta_content(html, "property", "og:title"),
        _extract_meta_content(html, "name", "twitter:title"),
        _extract_json_ld_field(html, "name"),
    ]
    for candidate in title_candidates:
        if candidate:
            title = candidate
            break
    if not title:
        title_match = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        if title_match:
            title = _clean_html_text(title_match.group(1))

    desc_candidates = [
        _extract_meta_content(html, "property", "og:description"),
        _extract_meta_content(html, "name", "description"),
        _extract_meta_content(html, "name", "twitter:description"),
        _extract_json_ld_field(html, "description"),
    ]
    for candidate in desc_candidates:
        if candidate:
            desc = candidate
            break

    ingredient_patterns = [
        r"(?:Ingredients|Ingredient|INGREDIENTS)\s*[:：]\s*(.*?)(?:<|Nutrition|Supplement Facts|Allergen|Directions|Warnings|Description|$)",
        r"(?:成分)\s*[:：]\s*(.*?)(?:<|營養|食用方法|警告|描述|$)",
        r'"ingredients?"\s*:\s*"(.*?)"',
    ]
    for pattern in ingredient_patterns:
        match = re.search(pattern, html, re.I | re.S)
        if match:
            ingredients_text = _clean_html_text(match.group(1))
            if ingredients_text:
                break
    if not ingredients_text:
        ingredients_text = _extract_material_context(html)

    warning_patterns = [
        r"(WARNING:.*?)(?:<|Directions|Ingredients|Description|$)",
        r"(Cancer and Reproductive Harm.*?)(?:<|Directions|Ingredients|Description|$)",
        r"(Keep out of reach of children.*?)(?:<|Directions|Ingredients|Description|$)",
        r'"warnings?"\s*:\s*"(.*?)"',
    ]
    for pattern in warning_patterns:
        match = re.search(pattern, html, re.I | re.S)
        if match:
            warning_text = _clean_html_text(match.group(1))
            if warning_text:
                break

    slug_title = _extract_generic_slug_title(url)
    title = title or slug_title
    parts = [part for part in [title, desc] if normalize_text(part)]
    product_text = " | ".join(parts)
    ingredients_text = _clean_url_field_text(ingredients_text, field="ingredients")
    warning_text = _clean_url_field_text(warning_text, field="claims")

    return {
        "product_text": product_text,
        "category": category,
        "ingredients_text": ingredients_text,
        "nutrition_text": _extract_nutrition_context(html),
        "warning_text": warning_text,
    }


def _extract_nutrition_context(text: str | None) -> str:
    if not text or extract_nutrition_text_from_readable is None:
        return ""
    readable = _clean_html_text(text)
    return extract_nutrition_text_from_readable(readable)


def _looks_like_food_context(product_text: str | None, category: str | None = None) -> bool:
    blob = normalize_text(" ".join(part for part in [product_text or "", category or ""] if part))
    return bool(
        re.search(
            r"\b(food|snack|cookie|biscuit|waffle|chips?|cracker|cereal|drink|beverage|tea|coffee|"
            r"kombucha|meat|sauce|candy|chocolate|bar|granola)\b",
            blob,
        )
    )


def _context_needs_label_enrichment(context: dict[str, Any]) -> bool:
    product_blob = normalize_text(" ".join(
        part for part in [context.get("product_text") or "", context.get("category") or ""] if part
    ))
    is_food = _looks_like_food_context(context.get("product_text"), context.get("category"))
    ingredient_priority = is_food or bool(
        re.search(r"\b(detergent|cleaner|disinfect|shampoo|conditioner|lotion|soap|cosmetic|personal care)\b", product_blob)
    )
    needs_ingredients = ingredient_priority and not normalize_text(context.get("ingredients_text"))
    needs_nutrition = is_food and not normalize_text(context.get("nutrition_text"))
    return needs_ingredients or needs_nutrition


def _merge_product_page_context(*contexts: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for context in contexts:
        if not context:
            continue
        for key, value in context.items():
            if key == "product_images":
                existing = list(merged.get(key) or [])
                for image_url in value or []:
                    if image_url and image_url not in existing:
                        existing.append(image_url)
                merged[key] = existing
                continue
            if isinstance(value, bool):
                merged[key] = bool(merged.get(key)) or value
                continue
            if value not in (None, "", []):
                merged[key] = value
    return merged


def _download_product_images(image_urls: list[str]) -> list[str]:
    if not image_urls:
        return []

    paths: list[str] = []
    output_dir = GEMMA4GOOD_PROJECT_ROOT / "outputs" / "temp_inputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    for index, image_url in enumerate(image_urls[:5]):
        try:
            response = requests.get(image_url, timeout=15, headers=headers)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            suffix = ".png"
            if "jpeg" in content_type or "jpg" in content_type:
                suffix = ".jpg"
            elif "webp" in content_type:
                suffix = ".webp"
            path = output_dir / f"url_label_scan_{index}{suffix}"
            path.write_bytes(response.content)
            paths.append(str(path))
        except Exception:
            continue
    return paths


def _merge_label_image_ocr(context: dict[str, Any], ocr_text: str) -> dict[str, Any]:
    updated = dict(context)
    if not normalize_text(ocr_text):
        return updated

    if extract_ingredient_text_from_readable is not None and not normalize_text(updated.get("ingredients_text")):
        ingredients = extract_ingredient_text_from_readable(ocr_text)
        if ingredients:
            updated["ingredients_text"] = ingredients

    if extract_nutrition_text_from_readable is not None and not normalize_text(updated.get("nutrition_text")):
        nutrition = extract_nutrition_text_from_readable(ocr_text)
        if nutrition:
            updated["nutrition_text"] = nutrition
            if extract_serving_size is not None:
                updated["serving_size"] = extract_serving_size(nutrition)

    updated["label_image_ocr_text"] = ocr_text[:2500]
    updated["label_image_scan_used"] = True
    return updated


def _enrich_context_from_product_images(context: dict[str, Any]) -> dict[str, Any]:
    if not context.get("product_images") or not _context_needs_label_enrichment(context):
        return context
    try:
        from mlx_engine import run_scribe_agent
    except Exception:
        return context

    image_paths = _download_product_images(list(context.get("product_images") or []))
    if not image_paths:
        return context
    try:
        ocr_text = run_scribe_agent(image_paths)
    except Exception:
        return context
    return _merge_label_image_ocr(context, ocr_text)


def _has_meaningful_product_text(text: str | None, url: str | None = None) -> bool:
    raw_text = (text or "").strip()
    normalized = normalize_text(raw_text)
    if not normalized:
        return False

    parsed = urlparse((url or "").strip())
    host_text = parsed.netloc.lower().replace("www.", "")
    normalized_host = normalize_text(host_text.replace(".", " "))

    pieces = [
        normalize_text(piece)
        for piece in re.split(r"\s*\|\s*", raw_text)
        if normalize_text(piece)
    ]
    informative_pieces = [piece for piece in pieces if piece != normalized_host]
    if not informative_pieces:
        return False

    informative_joined = " ".join(informative_pieces).strip()
    if informative_joined == normalized_host:
        return False

    if len(informative_joined) >= 16:
        return True
    return any(" " in piece and len(piece) >= 10 for piece in informative_pieces)


def _looks_like_amazon_block_page(html: str) -> bool:
    lowered = (html or "").lower()
    signals = [
        "503 - service unavailable error",
        "to discuss automated access to amazon data",
        "sorry! something went wrong. please go back and try again",
        "ref=cs_503_link",
    ]
    return any(signal in lowered for signal in signals)


def split_multi_value(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"\s*[;|]\s*", value.strip())
    return [part.strip() for part in parts if part.strip()]


def tokenize_match_text(value: str | None) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize_text(value))


def is_plausible_chemical_match(query_text: str, candidate_text: str) -> bool:
    normalized_query = normalize_text(query_text)
    normalized_candidate = normalize_text(candidate_text)
    if not normalized_query or not normalized_candidate:
        return False
    if normalized_query == normalized_candidate:
        return True

    query_tokens = tokenize_match_text(normalized_query)
    candidate_tokens = tokenize_match_text(normalized_candidate)
    if not query_tokens or not candidate_tokens:
        return False

    if len(query_tokens) == 1:
        return query_tokens[0] in candidate_tokens

    significant_tokens = [
        token
        for token in query_tokens
        if len(token) >= 4 and token not in GENERIC_CHEM_TOKENS
    ]
    if significant_tokens:
        candidate_token_set = set(candidate_tokens)
        if len(significant_tokens) <= 3:
            return all(token in candidate_token_set for token in significant_tokens)
        overlap_count = sum(1 for token in significant_tokens if token in candidate_token_set)
        return overlap_count >= max(2, int(len(significant_tokens) * 0.6))

    overlap = set(query_tokens) & set(candidate_tokens)
    return len(overlap) >= min(2, len(set(query_tokens)))


@dataclass
class ChemicalMatch:
    chemical_id: str | None
    preferred_name: str
    matched_text: str
    match_kind: str
    score: float


@dataclass
class ProductTypeMatch:
    product_type_id: str
    normalized_product_type: str
    mapped_product_category: str
    match_kind: str
    score: float


def get_connection(dsn: str | None = None) -> psycopg.Connection[Any]:
    final_dsn = dsn or os.getenv("GEMMA4GOOD_PG_DSN") or os.getenv("DATABASE_URL")
    if not final_dsn:
        raise RuntimeError(
            "Missing database connection string. Set GEMMA4GOOD_PG_DSN or DATABASE_URL."
        )
    conn = psycopg.connect(final_dsn, row_factory=dict_row)
    with conn.cursor() as cur:
        cur.execute("SET search_path TO gemma4good, public;")
    conn.commit()
    return conn


def find_chemical_matches(
    conn: psycopg.Connection[Any],
    query_text: str,
    *,
    limit: int = 10,
) -> list[ChemicalMatch]:
    normalized = normalize_text(query_text)
    sql = """
    WITH exact_hits AS (
        SELECT
            c.chemical_id,
            c.preferred_name,
            c.preferred_name AS matched_text,
            'exact_preferred_name' AS match_kind,
            1.0::float AS score
        FROM chemicals c
        WHERE md5(c.normalized_name) = md5(%(normalized)s)
          AND c.normalized_name = %(normalized)s
    ),
    alias_hits AS (
        SELECT
            c.chemical_id,
            c.preferred_name,
            a.alias_text AS matched_text,
            'alias' AS match_kind,
            similarity(a.alias_text, %(raw)s) AS score
        FROM chemical_aliases a
        JOIN chemicals c ON c.chemical_id = a.chemical_id
        WHERE a.normalized_alias = %(normalized)s
           OR a.alias_text %% %(raw)s
    ),
    fuzzy_hits AS (
        SELECT
            chemical_id,
            preferred_name,
            preferred_name AS matched_text,
            'fuzzy_preferred_name' AS match_kind,
            similarity(preferred_name, %(raw)s) AS score
        FROM chemicals
        WHERE preferred_name %% %(raw)s
    )
    SELECT *
    FROM (
        SELECT * FROM exact_hits
        UNION ALL
        SELECT * FROM alias_hits
        UNION ALL
        SELECT * FROM fuzzy_hits
    ) hits
    ORDER BY score DESC, preferred_name ASC
    LIMIT %(limit)s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"normalized": normalized, "raw": query_text, "limit": limit})
        rows = cur.fetchall()
    filtered_rows = [
        row
        for row in rows
        if is_plausible_chemical_match(query_text, row["matched_text"] or row["preferred_name"])
    ]

    deduped: list[dict[str, Any]] = []
    seen_keys: set[tuple[str | None, str]] = set()
    for row in filtered_rows:
        key = (row["chemical_id"], row["preferred_name"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(row)

    return [
        ChemicalMatch(
            chemical_id=row["chemical_id"],
            preferred_name=row["preferred_name"],
            matched_text=row["matched_text"],
            match_kind=row["match_kind"],
            score=float(row["score"]),
        )
        for row in deduped
    ]


def find_contextual_chemical_matches(
    conn: psycopg.Connection[Any],
    query_text: str,
    *,
    limit: int = 10,
) -> list[ChemicalMatch]:
    """Match known aliases that appear inside longer product/material text."""
    normalized = normalize_text(query_text)
    if not normalized:
        return []

    sql = """
    WITH alias_hits AS (
        SELECT
            c.chemical_id,
            c.preferred_name,
            a.alias_text AS matched_text,
            'context_alias' AS match_kind,
            length(a.normalized_alias)::float AS score
        FROM chemical_aliases a
        JOIN chemicals c ON c.chemical_id = a.chemical_id
        WHERE length(a.normalized_alias) >= 3
          AND position(a.normalized_alias in %(normalized)s) > 0
    ),
    preferred_hits AS (
        SELECT
            c.chemical_id,
            c.preferred_name,
            c.preferred_name AS matched_text,
            'context_preferred_name' AS match_kind,
            length(c.normalized_name)::float AS score
        FROM chemicals c
        WHERE length(c.normalized_name) >= 3
          AND position(c.normalized_name in %(normalized)s) > 0
    )
    SELECT *
    FROM (
        SELECT * FROM alias_hits
        UNION ALL
        SELECT * FROM preferred_hits
    ) hits
    ORDER BY score DESC, preferred_name ASC
    LIMIT %(limit)s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"normalized": normalized, "limit": limit})
        rows = cur.fetchall()

    deduped: list[dict[str, Any]] = []
    seen_keys: set[tuple[str | None, str]] = set()
    for row in rows:
        key = (row["chemical_id"], row["preferred_name"])
        if key in seen_keys:
            continue
        matched_text = normalize_text(row["matched_text"] or row["preferred_name"])
        if matched_text and not re.search(rf"(?<![a-z0-9]){re.escape(matched_text)}(?![a-z0-9])", normalized):
            continue
        seen_keys.add(key)
        deduped.append(row)

    return [
        ChemicalMatch(
            chemical_id=row["chemical_id"],
            preferred_name=row["preferred_name"],
            matched_text=row["matched_text"],
            match_kind=row["match_kind"],
            score=float(row["score"]),
        )
        for row in deduped
    ]


def find_material_context_chemical_matches(
    conn: psycopg.Connection[Any],
    query_text: str,
    *,
    limit: int = 12,
) -> list[ChemicalMatch]:
    """Match product/material phrases stored on chemical records."""
    normalized_query = normalize_text(query_text)
    if not normalized_query:
        return []

    sql = """
    SELECT
        chemical_id,
        preferred_name,
        common_product_types,
        likely_material_layers
    FROM chemicals
    WHERE COALESCE(common_product_types::text, '') <> ''
       OR COALESCE(likely_material_layers::text, '') <> '';
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    candidates: list[tuple[int, dict[str, Any], str]] = []
    for row in rows:
        phrases: list[str] = []
        for field in ["common_product_types", "likely_material_layers"]:
            field_value = row.get(field) or []
            if isinstance(field_value, list):
                phrases.extend(str(part).strip() for part in field_value if str(part).strip())
            else:
                phrases.extend(
                    part.strip()
                    for part in str(field_value).split(";")
                    if part.strip()
                )
        for phrase in phrases:
            normalized_phrase = normalize_text(phrase)
            if len(normalized_phrase) >= 4 and normalized_phrase in normalized_query:
                candidates.append((len(normalized_phrase), row, phrase))
                break

    deduped: list[ChemicalMatch] = []
    seen_ids: set[str | None] = set()
    for score, row, phrase in sorted(candidates, key=lambda item: item[0], reverse=True):
        if row["chemical_id"] in seen_ids:
            continue
        seen_ids.add(row["chemical_id"])
        deduped.append(
            ChemicalMatch(
                chemical_id=row["chemical_id"],
                preferred_name=row["preferred_name"],
                matched_text=phrase,
                match_kind="material_context",
                score=float(score),
            )
        )
        if len(deduped) >= limit:
            break
    return deduped


def find_product_type_matches(
    conn: psycopg.Connection[Any],
    query_text: str,
    *,
    limit: int = 10,
) -> list[ProductTypeMatch]:
    normalized = normalize_text(query_text)
    sql = """
    WITH exact_hits AS (
        SELECT
            p.product_type_id,
            p.normalized_product_type,
            p.mapped_product_category,
            'exact_product_type' AS match_kind,
            1.0::float AS score
        FROM product_types p
        WHERE p.normalized_product_type = %(normalized)s
    ),
    alias_hits AS (
        SELECT
            p.product_type_id,
            p.normalized_product_type,
            p.mapped_product_category,
            'alias' AS match_kind,
            similarity(a.alias_text, %(raw)s) AS score
        FROM product_type_aliases a
        JOIN product_types p ON p.product_type_id = a.product_type_id
        WHERE a.normalized_alias = %(normalized)s
           OR a.alias_text %% %(raw)s
    ),
    fuzzy_hits AS (
        SELECT
            product_type_id,
            normalized_product_type,
            mapped_product_category,
            'fuzzy_product_type' AS match_kind,
            similarity(normalized_product_type, %(normalized)s) AS score
        FROM product_types
        WHERE normalized_product_type %% %(normalized)s
    )
    SELECT *
    FROM (
        SELECT * FROM exact_hits
        UNION ALL
        SELECT * FROM alias_hits
        UNION ALL
        SELECT * FROM fuzzy_hits
    ) hits
    ORDER BY score DESC, normalized_product_type ASC
    LIMIT %(limit)s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"normalized": normalized, "raw": query_text, "limit": limit})
        rows = cur.fetchall()
    return [
        ProductTypeMatch(
            product_type_id=row["product_type_id"],
            normalized_product_type=row["normalized_product_type"],
            mapped_product_category=row["mapped_product_category"],
            match_kind=row["match_kind"],
            score=float(row["score"]),
        )
        for row in rows
    ]


def get_regulatory_signals(
    conn: psycopg.Connection[Any],
    *,
    chemical_ids: list[str] | None = None,
    product_category: str | None = None,
    region_query: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {"limit": limit}
    order_clauses = [
        "ban_flag DESC",
        "restriction_flag DESC",
        "warning_flag DESC",
    ]

    if chemical_ids:
        clauses.append("chemical_id = ANY(%(chemical_ids)s)")
        params["chemical_ids"] = chemical_ids
    if product_category:
        params["product_category"] = product_category
        params["product_scope_like"] = f"%{product_category}%"
        order_clauses.insert(
            0,
            "CASE WHEN product_category = %(product_category)s OR product_scope ILIKE %(product_scope_like)s THEN 1 ELSE 0 END DESC",
        )
    if region_query:
        clauses.append(
            "("
            "country_or_jurisdiction ILIKE %(region_like)s "
            "OR region_label ILIKE %(region_like)s "
            "OR source_authority ILIKE %(region_like)s"
            ")"
        )
        params["region_like"] = f"%{region_query}%"

    where_sql = "WHERE " + " AND ".join(clauses) if clauses else ""
    sql = """
    SELECT
        evidence_id,
        chemical_id,
        preferred_name,
        source_authority,
        source_type,
        country_or_jurisdiction,
        region_label,
        product_category,
        product_scope,
        regulation_or_list_name,
        regulatory_status,
        hazard_basis,
        warning_flag,
        ban_flag,
        restriction_flag,
        allowed_flag,
        hazard_classification_flag,
        threshold_value,
        threshold_unit,
        threshold_type,
        threshold_conditions,
        citation_title,
        citation_url
    FROM regulatory_evidence
    {where_sql}
    ORDER BY
        {order_sql},
        source_authority ASC,
        preferred_name ASC
    LIMIT %(limit)s;
    """.format(where_sql=where_sql, order_sql=", ".join(order_clauses))
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def get_warning_interpretations(
    conn: psycopg.Connection[Any],
    warning_text: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    sql = """
    SELECT
        warning_id,
        regime,
        warning_text_pattern,
        product_context,
        concern_level_default,
        what_it_legally_means,
        what_it_does_not_mean,
        when_to_take_more_seriously,
        when_not_to_overinterpret,
        suggested_user_action,
        similarity(warning_text_pattern, %(warning_text)s) AS score
    FROM warning_interpretations
    WHERE warning_text_pattern %% %(warning_text)s
       OR %(warning_text)s ILIKE ('%%' || warning_text_pattern || '%%')
    ORDER BY score DESC
    LIMIT %(limit)s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"warning_text": warning_text, "limit": limit})
        return list(cur.fetchall())


def get_literature_for_chemical_or_topic(
    conn: psycopg.Connection[Any],
    *,
    chemical_name: str | None = None,
    topic_name: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {"limit": limit}
    if chemical_name:
        clauses.append("chemical_or_material_scope ILIKE %(chem_like)s")
        params["chem_like"] = f"%{chemical_name}%"
    if topic_name:
        clauses.append("(topic_name ILIKE %(topic_like)s OR topic_id ILIKE %(topic_like)s)")
        params["topic_like"] = f"%{topic_name}%"
    where_sql = "WHERE " + " OR ".join(clauses) if clauses else ""
    sql = f"""
    SELECT
        literature_id,
        topic_id,
        topic_name,
        chemical_or_material_scope,
        evidence_type,
        evidence_strength,
        stance_direction,
        jurisdiction_or_body,
        claim_summary,
        important_limitations,
        citation_title,
        citation_url,
        publisher_or_journal,
        publication_year
    FROM literature_evidence
    {where_sql}
    ORDER BY publication_year DESC NULLS LAST, evidence_strength DESC NULLS LAST
    LIMIT %(limit)s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def build_grounding_context(
    conn: psycopg.Connection[Any],
    *,
    product_text: str | None = None,
    product_page_url: str | None = None,
    ingredients_text: str | None = None,
    warning_text: str | None = None,
    region_label: str | None = None,
) -> dict[str, Any]:
    url_context = fetch_product_page_context(product_page_url) if product_page_url else {}
    fetched_product_text = url_context.get("product_text", "")
    fetched_ingredients_text = url_context.get("ingredients_text", "")
    fetched_warning_text = url_context.get("warning_text", "")

    merged_product_text = " | ".join(
        part for part in [product_text or "", fetched_product_text] if normalize_text(part)
    )
    merged_ingredients_text = " | ".join(
        part for part in [ingredients_text or "", fetched_ingredients_text] if normalize_text(part)
    )
    merged_warning_text = " | ".join(
        part for part in [warning_text or "", fetched_warning_text] if normalize_text(part)
    )

    combined_product_text = product_text_with_link_clues(merged_product_text, product_page_url)
    product_matches = find_product_type_matches(conn, combined_product_text or "", limit=5) if combined_product_text else []

    # v26.9: Robust Tokenization for messy OCR
    candidate_ingredients = []
    if merged_ingredients_text:
        # Support full-width Asian punctuation, brackets, and common OCR noise
        candidate_ingredients = [
            chunk.strip()
            for chunk in re.split(r"[;,|\n：，。：；()（）<>\[\]{}*]+", merged_ingredients_text)
            if chunk.strip()
        ]

    # v26.9: Forensic Sub-string Matcher (API Path)
    # This is the most reliable way to find chemicals in noisy fragments.
    chemical_matches: list[ChemicalMatch] = []
    
    # Pre-fetch all active aliases from the database for sub-string scanning
    sql_aliases = """
        SELECT DISTINCT a.normalized_alias, c.chemical_id, c.preferred_name 
        FROM chemical_aliases a
        JOIN chemicals c ON c.chemical_id = a.chemical_id
        WHERE length(a.normalized_alias) >= 4;
    """
    with conn.cursor() as cur:
        cur.execute(sql_aliases)
        db_aliases = cur.fetchall()

    # Create ultra-clean versions for scanning (no punctuation)
    ing_clean = re.sub(r"[^a-z0-9]+", " ", normalize_text(merged_ingredients_text))
    prod_clean = re.sub(r"[^a-z0-9]+", " ", normalize_text(combined_product_text))
    search_space = f" {ing_clean} {prod_clean} "
    
    for row in db_aliases:
        alias = row["normalized_alias"]
        # Wrap in spaces to avoid partial word matches (e.g., "red" in "ingredients")
        # but the alias itself often has spaces like "red 40"
        if f" {alias} " in search_space or f" {alias}lake " in search_space:
            chemical_matches.append(ChemicalMatch(
                chemical_id=row["chemical_id"],
                preferred_name=row["preferred_name"],
                matched_text=alias,
                match_kind="forensic_substring",
                score=float(len(alias) * 10)
            ))

    # Strategy 2: Supplemental Evidence Scanner
    sql_ev = "SELECT DISTINCT chemical_id, preferred_name FROM regulatory_evidence WHERE length(preferred_name) >= 5;"
    with conn.cursor() as cur:
        cur.execute(sql_ev)
        ev_names = cur.fetchall()
        
    for row in ev_names:
        name = normalize_text(row["preferred_name"])
        name_clean = re.sub(r"[^a-z0-9]+", " ", name)
        if name_clean and f" {name_clean} " in search_space:
            chemical_matches.append(ChemicalMatch(
                chemical_id=row["chemical_id"],
                preferred_name=row["preferred_name"],
                matched_text=name,
                match_kind="evidence_substring",
                score=float(len(name) * 8)
            ))

    deduped_chemical_matches: list[ChemicalMatch] = []
    seen_ids: set[str | None] = set()
    # Prioritize longest matches (more specific)
    for item in sorted(chemical_matches, key=lambda x: x.score, reverse=True):
        if item.chemical_id in seen_ids:
            continue
        seen_ids.add(item.chemical_id)
        deduped_chemical_matches.append(item)
    chemical_matches = deduped_chemical_matches

    dedup_chemical_ids = []
    seen = set()
    for item in chemical_matches:
        if item.chemical_id and item.chemical_id not in seen:
            seen.add(item.chemical_id)
            dedup_chemical_ids.append(item.chemical_id)

    top_category = product_matches[0].mapped_product_category if product_matches else None
    direct_evidence_rows = (
        get_regulatory_signals(
            conn,
            chemical_ids=dedup_chemical_ids,
            product_category=top_category,
            # Keep cross-jurisdiction evidence available for comparison. The caller's
            # region can still shape the recommendation layer, but retrieval should not
            # hide EU/FDA/Prop65 differences from Gemma before reasoning starts.
            region_query=None,
            limit=25,
        )
        if dedup_chemical_ids
        else []
    )
    category_level_evidence_rows = (
        get_regulatory_signals(
            conn,
            product_category=top_category,
            region_query=region_label,
            limit=10,
        )
        if top_category
        else []
    )
    warning_rows = get_warning_interpretations(conn, merged_warning_text, limit=10) if merged_warning_text else []

    literature_rows: list[dict[str, Any]] = []
    if chemical_matches:
        literature_rows = get_literature_for_chemical_or_topic(
            conn,
            chemical_name=chemical_matches[0].preferred_name,
            limit=10,
        )
    chemical_text_for_model = " | ".join(
        item.preferred_name for item in chemical_matches[:5] if item.preferred_name
    )
    product_label_model = run_product_label_model(
        product_text=combined_product_text,
        ingredients_text=merged_ingredients_text,
        warning_text=merged_warning_text,
        chemical_text=chemical_text_for_model,
    )
    food_processing_profile = infer_food_processing_profile(
        product_text=combined_product_text,
        ingredients_text=merged_ingredients_text,
        warning_text=merged_warning_text,
    )
    if food_processing_profile.get("suppress_category_chemical_hypotheses") and not chemical_matches and not warning_rows:
        product_label_model["candidate_chemical_linkages"] = []

    return {
        "product_page_url": product_page_url,
        "url_context": url_context,
        "product_matches": [item.__dict__ for item in product_matches],
        "chemical_matches": [item.__dict__ for item in chemical_matches],
        "product_label_model": product_label_model,
        "candidate_chemical_linkages": product_label_model.get("candidate_chemical_linkages", []),
        "food_processing_profile": food_processing_profile,
        "regulatory_evidence": direct_evidence_rows or category_level_evidence_rows,
        "direct_regulatory_evidence": direct_evidence_rows,
        "category_level_regulatory_evidence": category_level_evidence_rows,
        "warning_interpretations": warning_rows,
        "literature_evidence": literature_rows,
    }


def infer_use_material(
    *,
    product_text: str | None,
    ingredients_text: str | None,
    product_matches: list[dict[str, Any]],
) -> dict[str, str]:
    text = normalize_text(" ".join(filter(None, [product_text, ingredients_text])))
    category_hint = " ".join(match.get("mapped_product_category", "") for match in product_matches).lower()

    if any(
        token in text
        for token in [
            "bib",
            "teether",
            "toy",
            "baby",
            "child",
            "diaper",
            "wipes",
            "training pants",
            "walker",
            "stroller",
            "nipple",
        ]
    ):
        product_use_category = "children_products"
    elif any(
        token in text
        for token in [
            "conditioner",
            "shampoo",
            "body wash",
            "hair care",
            "hair",
            "skin care",
            "lotion",
            "moisturizer",
            "serum",
            "deodorant",
            "cosmetic",
            "sunscreen",
            "makeup",
            "fragrance",
            "parfum",
        ]
    ):
        product_use_category = "personal_care"
    elif any(
        token in text
        for token in [
            "mug",
            "cup",
            "plate",
            "bowl",
            "food container",
            "cookware",
            "tumbler",
            "water bottle",
            "food thermometer",
            "meat thermometer",
            "kitchen scale",
        ]
    ):
        product_use_category = "food_contact"
    elif any(
        token in text
        for token in [
            "cleaner",
            "cleaning",
            "disinfect",
            "degreaser",
            "bleach",
            "detergent",
            "fabric protector",
            "stain resistant",
            "odor remover",
            "air freshener",
            "spray",
            "solvent",
            "softener",
            "water shield",
            "stain remover",
            "upholstery",
        ]
    ):
        product_use_category = "household"
    elif any(
        token in text
        for token in [
            "protein",
            "supplement",
            "capsule",
            "powder",
            "snack",
            "candy",
            "food",
            "drink",
            "jam",
            "jelly",
            "spread",
            "seasoning",
            "salt",
            "sauce",
            "chips",
            "bar",
            "granola",
            "cereal",
            "coffee",
            "bean",
            "beans",
            "seed",
            "seeds",
            "beverage",
            "shake",
            "oil",
            "pods",
            "pod",
            "mct",
            "collagen",
            "creatine",
        ]
    ):
        product_use_category = "food"
    elif any(token in text for token in ["lipstick", "cream"]):
        product_use_category = "personal_care"
    elif any(token in text for token in ["bag", "wallet", "backpack", "pouch", "accessory"]):
        product_use_category = "bags_accessories"
    elif any(token in text for token in ["receipt", "paper", "air freshener", "candle", "furniture"]):
        product_use_category = "household"
    elif any(token in text for token in ["thermometer", "bottle"]):
        product_use_category = "food_contact"
    elif any(token in text for token in ["cable", "charger", "electronics", "wire", "fan"]):
        product_use_category = "electronics"
    elif any(token in text for token in ["underwear", "t-shirt", "shirts", "shirt", "short", "shorts", "clog", "wearable"]):
        product_use_category = "bags_accessories"
    elif "child care" in category_hint:
        product_use_category = "children_products"
    else:
        product_use_category = "unknown"

    if any(token in text for token in ["pvc", "vinyl", "dehp", "dinp", "soft plastic"]):
        material_subcategory = "pvc_vinyl"
    elif any(token in text for token in ["ceramic", "stoneware", "porcelain"]):
        material_subcategory = "ceramic"
    elif any(token in text for token in ["receipt", "thermal paper", "paper"]):
        material_subcategory = "paper"
    elif any(token in text for token in ["powder", "capsule", "seasoning", "salt", "spice"]):
        material_subcategory = "powdered_or_capsule_form"
    elif any(
        token in text
        for token in [
            "jam",
            "jelly",
            "spread",
            "snack",
            "candy",
            "chips",
            "sauce",
            "drink",
            "granola",
            "bar",
            "cereal",
            "coffee",
            "bean",
            "beans",
            "seed",
            "seeds",
            "shake",
            "oil",
            "beverage",
            "chocolate",
        ]
    ):
        material_subcategory = "ingestible_food_matrix"
    elif any(token in text for token in ["metal", "stainless", "aluminum", "brass"]):
        material_subcategory = "metal"
    elif any(token in text for token in ["glass"]):
        material_subcategory = "glass"
    elif any(token in text for token in ["cotton", "fabric", "cloth", "shirt", "shorts", "underwear", "diaper", "wipes", "vest"]):
        material_subcategory = "textile"
    elif product_use_category == "personal_care" and any(token in text for token in ["water", "aqua", "alcohol", "fragrance", "parfum", "conditioner", "shampoo", "lotion", "cream"]):
        material_subcategory = "personal_care_formula"
    elif any(token in text for token in ["silicone", "plastic", "polymer", "neoprene", "rubber", "foam", "walker", "stroller", "fan", "toy", "goggles", "band"]):
        material_subcategory = "mixed_material"
    elif any(token in text for token in ["leather", "faux leather", "pu leather"]):
        material_subcategory = "leather_faux_leather"
    else:
        material_subcategory = "unknown"

    return {
        "product_use_category": product_use_category,
        "material_subcategory": material_subcategory,
    }


MODEL_TO_APP_CATEGORY = {
    "food": "food",
    "food_contact": "food_contact",
    "children_products": "children_products",
    "household_cleaner": "household",
    "personal_care": "personal_care",
    "textile_or_soft_goods": "bags_accessories",
    "furniture_or_building": "household",
}


def run_product_label_model(
    *,
    product_text: str | None,
    ingredients_text: str | None,
    warning_text: str | None,
    chemical_text: str | None = "",
) -> dict[str, Any]:
    if predict_product_labels_with_linkages is None:
        return {
            "available": False,
            "error": "product_label_classifier is not importable",
            "label_predictions": {},
            "candidate_chemical_linkages": [],
        }
    try:
        result = predict_product_labels_with_linkages(
            product_text=product_text or "",
            ingredient_text=ingredients_text or "",
            warning_text=warning_text or "",
            chemical_text=chemical_text or "",
        )
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
            "label_predictions": {},
            "candidate_chemical_linkages": [],
        }
    return {"available": True, **result}


RAW_MEAT_TERMS = (
    "beef",
    "steak",
    "pork",
    "lamb",
    "veal",
    "chicken",
    "turkey",
    "duck",
    "goose",
    "breast",
    "thigh",
    "drumstick",
    "sirloin",
    "ribeye",
    "ground meat",
    "minced meat",
    "meat",
)

PROCESSED_FOOD_TERMS = (
    "seasoned",
    "marinated",
    "smoked",
    "cured",
    "breaded",
    "battered",
    "nuggets",
    "sausage",
    "bacon",
    "ham",
    "jerky",
    "deli",
    "ready meal",
    "microwave",
    "instant",
    "sauce",
    "flavor",
    "flavored",
    "spicy",
    "bbq",
    "barbecue",
)

FOOD_ADDITIVE_TERMS = (
    "nitrite",
    "nitrate",
    "phosphate",
    "benzoate",
    "sorbate",
    "sulfite",
    "msg",
    "monosodium glutamate",
    "artificial color",
    "red 40",
    "yellow 5",
    "preservative",
    "flavoring",
    "modified starch",
    "maltodextrin",
)


def infer_food_processing_profile(
    *,
    product_text: str | None,
    ingredients_text: str | None,
    warning_text: str | None,
) -> dict[str, Any]:
    combined = normalize_text(" ".join(filter(None, [product_text, ingredients_text, warning_text])))
    ingredients_norm = normalize_text(ingredients_text)
    if not combined:
        return {
            "applies": False,
            "processing_level": "unknown",
            "container_contact_relevance": "unknown",
            "suppress_category_chemical_hypotheses": False,
            "rationale": "",
        }

    has_raw_meat_signal = any(term in combined for term in RAW_MEAT_TERMS)
    has_processed_signal = any(term in combined for term in PROCESSED_FOOD_TERMS)
    has_additive_signal = any(term in combined for term in FOOD_ADDITIVE_TERMS)
    has_ingredient_list = bool(ingredients_norm)
    ingredient_parts = [part.strip() for part in re.split(r"[,;|]", ingredients_norm) if part.strip()]
    single_or_missing_ingredient = not ingredient_parts or len(ingredient_parts) <= 1
    frozen_signal = "frozen" in combined

    if has_raw_meat_signal and not has_processed_signal and not has_additive_signal and single_or_missing_ingredient:
        return {
            "applies": True,
            "processing_level": "minimally_processed_raw_meat",
            "container_contact_relevance": "secondary_context_only",
            "suppress_category_chemical_hypotheses": True,
            "rationale": (
                "Product text looks like plain meat with no visible additive, curing, seasoning, or warning signal. "
                "Do not infer food additives or Prop 65 chemicals from broad food-category patterns alone."
            ),
            "signals": {
                "raw_meat_signal": True,
                "frozen_signal": frozen_signal,
                "ingredient_list_present": has_ingredient_list,
            },
        }

    if has_processed_signal or has_additive_signal or len(ingredient_parts) >= 3:
        return {
            "applies": True,
            "processing_level": "processed_or_formula_food",
            "container_contact_relevance": "consider_if_packaging_or_warning_evidence_exists",
            "suppress_category_chemical_hypotheses": False,
            "rationale": "Product text or ingredients suggest a formulated or processed food where additive and processing-pathway checks are more relevant.",
            "signals": {
                "processed_signal": has_processed_signal,
                "additive_signal": has_additive_signal,
                "ingredient_count": len(ingredient_parts),
            },
        }

    return {
        "applies": True,
        "processing_level": "food_processing_unknown",
        "container_contact_relevance": "context_only_without_packaging_evidence",
        "suppress_category_chemical_hypotheses": False,
        "rationale": "Food category detected, but processing level is not clear from available text.",
        "signals": {
            "raw_meat_signal": has_raw_meat_signal,
            "frozen_signal": frozen_signal,
            "ingredient_list_present": has_ingredient_list,
        },
    }


def apply_product_label_category_hint(
    category_info: dict[str, str],
    label_model_result: dict[str, Any],
) -> dict[str, str]:
    updated = dict(category_info)
    prediction = (label_model_result.get("label_predictions") or {}).get("product_category") or {}
    predicted_label = prediction.get("label")
    confidence = float(prediction.get("confidence") or 0)
    mapped = MODEL_TO_APP_CATEGORY.get(predicted_label or "")
    if mapped and confidence >= 0.65 and updated.get("product_use_category") == "unknown":
        updated["product_use_category"] = mapped
        updated["category_source"] = "product_label_classifier"
        updated["category_source_confidence"] = f"{confidence:.4f}"
    else:
        updated["category_source"] = updated.get("category_source", "rules")

    if updated.get("material_subcategory") == "unknown":
        if mapped == "food":
            updated["material_subcategory"] = "ingestible_food_matrix"
        elif predicted_label == "textile_or_soft_goods":
            updated["material_subcategory"] = "textile"
    return updated


def fetch_product_page_context(product_page_url: str | None) -> dict[str, Any]:
    raw_url = (product_page_url or "").strip()
    amazon_slug_title = _extract_amazon_slug_title(raw_url) if is_amazon_url(raw_url) else ""
    generic_slug_title = _extract_generic_slug_title(raw_url)
    fallback_title = amazon_slug_title or generic_slug_title
    url = normalize_product_page_url(raw_url)
    if not url:
        return {
            "fetch_attempted": False,
            "fetch_success": False,
            "fetch_error": "",
            "normalized_url": "",
            "product_text": "",
            "category": "",
            "ingredients_text": "",
            "nutrition_text": "",
            "warning_text": "",
        }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    candidate_urls = amazon_fetch_candidates(url) if is_amazon_url(url) else [url]
    fetch_errors: list[str] = []
    best_partial: dict[str, Any] = {}

    for candidate_url in candidate_urls:
        try:
            html = fetch_url_html(candidate_url, headers)
        except Exception as exc:
            fetch_errors.append(f"{candidate_url}: {exc}")
            continue

        amazon_blocked = is_amazon_url(candidate_url) and _looks_like_amazon_block_page(html)

        if is_amazon_url(candidate_url):
            extracted = _extract_amazon_context(html, candidate_url) if not amazon_blocked else {
                "product_text": amazon_slug_title,
                "category": "",
                "ingredients_text": "",
                "nutrition_text": "",
                "warning_text": "",
            }
            product_text = extracted["product_text"] or amazon_slug_title
            category = extracted.get("category", "")
            ingredients_text = extracted["ingredients_text"]
            nutrition_text = extracted.get("nutrition_text", "")
            warning_text = extracted["warning_text"]
        else:
            extracted = _extract_generic_context(html, candidate_url)
            product_text = extracted["product_text"] or generic_slug_title
            category = extracted.get("category", "")
            ingredients_text = extracted["ingredients_text"]
            nutrition_text = extracted.get("nutrition_text", "")
            warning_text = extracted["warning_text"]

        if is_amazon_url(candidate_url) and product_text and not normalize_text(ingredients_text):
            if not best_partial:
                best_partial = {
                    "fetch_attempted": True,
                    "fetch_success": True,
                    "fetch_error": "amazon_ingredients_missing",
                    "normalized_url": candidate_url,
                    "product_text": product_text,
                    "category": category,
                    "ingredients_text": ingredients_text,
                    "nutrition_text": nutrition_text,
                    "warning_text": warning_text,
                    "amazon_blocked": amazon_blocked,
                }
            fetch_errors.append(f"{candidate_url}: product found but ingredients dropdown was not extracted")
            continue

        if product_text or ingredients_text or nutrition_text or warning_text:
            direct_context = {
                "fetch_attempted": True,
                "fetch_success": True,
                "fetch_error": "amazon_blocked_503" if amazon_blocked else "",
                "normalized_url": candidate_url,
                "product_text": product_text,
                "category": category,
                "ingredients_text": ingredients_text,
                "nutrition_text": nutrition_text,
                "warning_text": warning_text,
                "amazon_blocked": amazon_blocked,
            }
            if _context_needs_label_enrichment(direct_context):
                best_partial = _merge_product_page_context(best_partial, direct_context)
                fetch_errors.append(f"{candidate_url}: product found but label details were incomplete")
                continue
            return direct_context
        fetch_errors.append(f"{candidate_url}: fetched but no usable product fields")

    browser_context = _browser_fetch_product_page_context(url, fallback_title=fallback_title)
    if browser_context:
        enriched_browser_context = _enrich_context_from_product_images(browser_context)
        if best_partial:
            return _merge_product_page_context(best_partial, enriched_browser_context)
        return enriched_browser_context

    if best_partial:
        best_partial["fetch_error"] = " | ".join(fetch_errors)
        return best_partial

    return {
        "fetch_attempted": True,
        "fetch_success": False,
        "fetch_error": " | ".join(fetch_errors),
        "normalized_url": url,
        "product_text": fallback_title,
        "category": "",
        "ingredients_text": "",
        "nutrition_text": "",
        "warning_text": "",
        "amazon_blocked": is_amazon_url(url),
    }


def _browser_fetch_product_page_context(url: str, *, fallback_title: str = "") -> dict[str, Any]:
    """Rendered-DOM fallback for retailer pages that hide facts behind accordions."""
    try:
        from browser_fetcher import BrowserFetcher

        browser_data = BrowserFetcher(headless=True).fetch(url)
    except Exception as exc:
        return {
            "fetch_attempted": True,
            "fetch_success": False,
            "fetch_error": f"browser_fallback_failed: {exc}",
            "normalized_url": url,
            "product_text": fallback_title,
            "category": "",
            "ingredients_text": "",
            "nutrition_text": "",
            "warning_text": "",
            "amazon_blocked": is_amazon_url(url),
        }

    product_text = (browser_data.get("product_name") or "").strip() or fallback_title
    ingredients_text = (browser_data.get("ingredients") or "").strip()
    nutrition_text = (browser_data.get("nutrition_text") or "").strip()
    warning_text = (browser_data.get("warnings") or "").strip() or (browser_data.get("claims") or "").strip()
    category = (browser_data.get("category") or "").strip()
    has_useful_content = any(
        normalize_text(value)
        for value in [product_text, ingredients_text, nutrition_text, warning_text]
    )
    if not has_useful_content:
        return {}
    return {
        "fetch_attempted": True,
        "fetch_success": True,
        "fetch_error": "browser_fallback_blocked" if browser_data.get("is_blocked") else "",
        "normalized_url": url,
        "product_text": product_text,
        "category": category,
        "ingredients_text": ingredients_text,
        "nutrition_text": nutrition_text,
        "warning_text": warning_text,
        "amazon_blocked": bool(browser_data.get("is_blocked")),
        "fetch_strategy": "browser_fallback",
        "product_images": list(browser_data.get("product_images") or []),
    }


def assess_input_sufficiency(
    *,
    input_mode: str | None,
    product_name: str | None,
    product_page_url: str | None,
    raw_ocr_text: str | None,
    ingredients_text: str | None,
    warning_text: str | None,
    url_context: dict[str, Any] | None,
) -> dict[str, Any]:
    mode = normalize_text(input_mode) or "unknown"
    product_present = bool(normalize_text(product_name))
    ocr_present = len(normalize_text(raw_ocr_text)) >= 20
    ingredients_present = len(normalize_text(ingredients_text)) >= 8
    warning_present = len(normalize_text(warning_text)) >= 8
    url_present = bool(normalize_text(product_page_url))
    url_success = bool((url_context or {}).get("fetch_success"))
    meaningful_product_context = _has_meaningful_product_text(
        (url_context or {}).get("product_text"),
        (url_context or {}).get("normalized_url") or product_page_url,
    )
    url_has_content = bool(
        meaningful_product_context
        or normalize_text((url_context or {}).get("ingredients_text"))
        or normalize_text((url_context or {}).get("warning_text"))
    )
    url_ingredients_present = bool(normalize_text((url_context or {}).get("ingredients_text")))
    url_looks_like_food = _looks_like_food_context(
        " ".join(
            part
            for part in [
                product_name or "",
                (url_context or {}).get("product_text") or "",
            ]
            if part
        ),
        (url_context or {}).get("category"),
    )

    if mode == "image":
        if ocr_present:
            return {
                "can_proceed": True,
                "status": "sufficient",
                "recommended_next_step": "continue_with_category_and_grounded_retrieval",
                "reason": "Image flow has enough reviewed OCR text to continue.",
            }
        return {
            "can_proceed": False,
            "status": "needs_better_input",
            "recommended_next_step": "ask_for_better_images_or_try_url_or_text",
            "reason": "The image path did not produce enough readable text. Ask for clearer images or switch to URL/text input.",
        }

    if mode == "url":
        amazon_blocked = bool((url_context or {}).get("amazon_blocked")) or (
            "amazon_blocked_503" in normalize_text((url_context or {}).get("fetch_error"))
        )
        if url_present and url_looks_like_food and not ingredients_present and not url_ingredients_present:
            return {
                "can_proceed": False,
                "status": "needs_food_ingredients",
                "recommended_next_step": "ask_for_ingredient_image_or_paste_text",
                "reason": (
                    "This appears to be a food product, but the webpage did not provide a readable ingredient list. "
                    "Ask the user to upload a clear photo of the ingredient panel or paste the ingredient text before analysis."
                ),
            }
        if url_present and url_success and url_has_content:
            return {
                "can_proceed": True,
                "status": "sufficient",
                "recommended_next_step": "continue_with_url_grounding",
                "reason": "The product URL returned readable product context.",
            }
        if url_present and meaningful_product_context:
            return {
                "can_proceed": True,
                "status": "partial_context",
                "recommended_next_step": "continue_with_url_grounding_using_title_or_slug_context",
                "reason": "The URL returned only partial product context, but there is still enough product title or slug information to continue with a limited grounded pass.",
            }
        if amazon_blocked:
            return {
                "can_proceed": False,
                "status": "blocked_by_site",
                "recommended_next_step": "ask_for_amazon_title_plus_url_or_images_or_text",
                "reason": "Amazon returned a bot-block or 503 page instead of a readable product page. Ask the user to paste the product title or description in the same message, or switch to product images / typed text.",
            }
        return {
            "can_proceed": False,
            "status": "needs_better_input",
            "recommended_next_step": "ask_to_reenter_url_or_try_images_or_text",
            "reason": "The URL could not be read well enough. Ask the user to retry the link or switch to images/text.",
        }

    if mode == "text":
        if product_present and (ocr_present or ingredients_present or warning_present):
            return {
                "can_proceed": True,
                "status": "sufficient",
                "recommended_next_step": "continue_with_text_grounding",
                "reason": "The text path includes enough product and description detail to continue.",
            }
        return {
            "can_proceed": False,
            "status": "needs_better_input",
            "recommended_next_step": "ask_for_more_text_or_recommend_url_or_images",
            "reason": "The text input is too incomplete to support a grounded answer. Ask for a fuller product description, a URL, or images.",
        }

    return {
        "can_proceed": False,
        "status": "unknown_mode",
        "recommended_next_step": "ask_user_to_choose_image_url_or_text_mode",
        "reason": "The app needs an explicit input mode to decide how to continue.",
    }


def extract_handling_caution_signal(text: str | None) -> dict[str, Any]:
    normalized = normalize_text(text)
    matched_terms: list[str] = []
    term_map = {
        "gloves": ["gloves", "wear gloves"],
        "mask": ["mask", "respirator"],
        "eye_protection": ["eye protection", "goggles"],
        "ventilation": ["ventilation", "well ventilated", "well-ventilated"],
        "avoid_inhalation": ["avoid inhalation", "do not inhale", "vapor", "fume"],
        "keep_away_from_children": ["keep away from children", "keep out of reach of children"],
    }
    for label, variants in term_map.items():
        if any(variant in normalized for variant in variants):
            matched_terms.append(label)

    return {
        "has_handling_caution": bool(matched_terms),
        "matched_terms": matched_terms,
        "requires_protective_gear": any(term in matched_terms for term in ["gloves", "mask", "eye_protection"]),
        "has_inhalation_signal": any(term in matched_terms for term in ["mask", "ventilation", "avoid_inhalation"]),
    }


def get_serving_recommendation(
    conn: psycopg.Connection[Any],
    *,
    product_use_category: str,
    material_subcategory: str,
) -> dict[str, Any] | None:
    sql = """
    SELECT *
    FROM serving_recommendations
    WHERE product_use_category = %(product_use_category)s
      AND material_subcategory = %(material_subcategory)s
    ORDER BY total_unique_notices DESC NULLS LAST
    LIMIT 1;
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            {
                "product_use_category": product_use_category,
                "material_subcategory": material_subcategory,
            },
        )
        row = cur.fetchone()
    return dict(row) if row else None


def derive_recommendation_bucket(
    *,
    regulatory_evidence: list[dict[str, Any]],
    chemical_matches: list[dict[str, Any]],
    recommendation_row: dict[str, Any] | None,
    warning_interpretations: list[dict[str, Any]],
    product_use_category: str,
    material_subcategory: str,
    ingredients_text: str | None,
    warning_text: str | None,
) -> dict[str, Any]:
    text = normalize_text(" ".join(filter(None, [ingredients_text, warning_text])))
    has_direct_match = bool(chemical_matches)
    has_ban = has_direct_match and any(row.get("ban_flag") for row in regulatory_evidence)
    has_restriction = has_direct_match and any(row.get("restriction_flag") for row in regulatory_evidence)
    has_warning = has_direct_match and any(row.get("warning_flag") for row in regulatory_evidence)
    has_prop65 = has_direct_match and any((row.get("source_authority") or "").lower() == "oehha" for row in regulatory_evidence)
    has_category_level_signal = (not has_direct_match) and bool(regulatory_evidence)
    handling_caution = extract_handling_caution_signal(warning_text)
    has_label_warning_context = bool(warning_interpretations) or bool(normalize_text(warning_text))
    looks_like_cleaner_or_spray = any(
        token in text
        for token in ["cleaner", "cleaning", "disinfect", "degreaser", "bleach", "detergent", "spray", "solvent", "fabric protector", "stain resistant"]
    )

    if has_ban or (has_restriction and product_use_category in {"children_products", "food_contact"}):
        bucket = "opt_for_other_product"
        reason = "A restriction or ban signal intersects with a higher-contact use context."
    elif (
        product_use_category == "children_products"
        and has_direct_match
        and any(
            token in text
            for token in [
                "formaldehyde",
                "lead",
                "cadmium",
                "dehp",
                "dinp",
                "dbp",
                "bpa",
                "bisphenol",
                "phthalate",
                "phthalates",
            ]
        )
    ):
        bucket = "opt_for_other_product"
        reason = "A direct chemical-match signal appears in a child-use context where substitution is more appropriate."
    elif material_subcategory == "pvc_vinyl" and product_use_category in {"children_products", "food_contact"}:
        bucket = "opt_for_other_product"
        reason = "Soft vinyl or PVC in child or direct-contact products is a stronger substitution case."
    elif handling_caution["has_handling_caution"] and looks_like_cleaner_or_spray:
        bucket = "rare_use_may_be_okay_but_limit_repeated_exposure"
        reason = "The label itself calls for ventilation or protective gear, so this looks better suited to careful occasional use than casual repeated exposure."
    elif has_category_level_signal and not has_label_warning_context:
        bucket = "limited_signal_found"
        reason = "The current lookup shows only category-level notice patterns and no direct match to the provided ingredient or material."
    elif any(token in text for token in ["titanium dioxide", "e171", "pfas", "fluoropolymer"]) or (
        recommendation_row and (recommendation_row.get("recommendation_priority") or "").lower() == "highest"
        and product_use_category in {"food", "food_contact"}
        and has_direct_match
    ):
        bucket = "emerging_research_caution"
        reason = "This looks like an area where scientific or cross-jurisdiction disagreement deserves extra caution."
    elif has_warning or has_prop65 or has_label_warning_context:
        bucket = "rare_use_may_be_okay_but_limit_repeated_exposure"
        reason = "There is a warning-style signal, but not an immediate product-specific ban in the current lookup."
    else:
        bucket = "limited_signal_found"
        reason = "No strong current warning or ban signal was found in the current lookup."

    return {
        "recommendation_bucket": bucket,
        "recommendation_reason": reason,
        "handling_caution_signal": {
            **handling_caution,
            "has_direct_chemical_match": has_direct_match,
            "has_category_level_signal_only": has_category_level_signal and not has_label_warning_context,
        },
    }


def summarize_concern_sources(regulatory_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    results: list[dict[str, Any]] = []
    for row in regulatory_evidence:
        key = (
            row.get("source_authority") or "",
            row.get("country_or_jurisdiction") or "",
            row.get("regulatory_status") or "",
        )
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "source_authority": row.get("source_authority"),
                "country_or_jurisdiction": row.get("country_or_jurisdiction"),
                "regulatory_status": row.get("regulatory_status"),
                "hazard_basis": row.get("hazard_basis"),
                "citation_url": row.get("citation_url"),
            }
        )
    return results


def annotate_candidate_chemical_linkages(
    linkages: list[dict[str, Any]],
    *,
    has_direct_chemical_match: bool,
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for item in linkages:
        row = dict(item)
        row["evidence_level"] = "direct_or_label_supported" if has_direct_chemical_match else "category_model_hypothesis"
        row["display_caveat"] = (
            "Direct ingredient/material text matched a chemical in the database."
            if has_direct_chemical_match
            else "Category-level hypothesis only; do not describe these chemicals as present in this exact product without label, ingredient, material, or warning evidence."
        )
        if not has_direct_chemical_match:
            row["top_chemicals"] = row.get("top_chemicals", [])[:3]
        annotated.append(row)
    return annotated


def infer_review_reasons(
    *,
    category_info: dict[str, str],
    recommendation: dict[str, Any],
    evidence_scope_summary: dict[str, Any],
    user_corrected_text: bool = False,
    user_corrected_category: bool = False,
    raw_ocr_text: str | None = None,
    product_name: str | None = None,
    ingredients_text: str | None = None,
    warning_text: str | None = None,
) -> list[str]:
    reasons: list[str] = []
    if category_info.get("product_use_category") == "unknown":
        reasons.append("unknown_product_category")
    if category_info.get("material_subcategory") == "unknown":
        reasons.append("unknown_material_subcategory")
    if user_corrected_text:
        reasons.append("user_corrected_ocr_text")
    if user_corrected_category:
        reasons.append("user_corrected_category")
    if evidence_scope_summary.get("has_category_level_signal_only"):
        reasons.append("category_level_signal_only")
    if recommendation.get("recommendation_bucket") in {"insufficient_info", "limited_signal_found"}:
        reasons.append("limited_or_insufficient_signal")

    normalized_ocr = normalize_text(raw_ocr_text)
    if raw_ocr_text and len(normalized_ocr) < 20:
        reasons.append("short_or_sparse_ocr")

    if not normalize_text(ingredients_text) and category_info.get("product_use_category") in {"food", "household"}:
        reasons.append("missing_priority_ingredients")
    if (
        not normalize_text(ingredients_text)
        and not normalize_text(warning_text)
        and category_info.get("product_use_category") in {"food_contact", "bags_accessories", "children_products"}
    ):
        reasons.append("missing_material_or_warning_detail")

    if not normalize_text(product_name) and not normalize_text(raw_ocr_text):
        reasons.append("missing_core_product_signal")
    return sorted(set(reasons))


def enqueue_review_case(
    conn: psycopg.Connection[Any],
    *,
    source_flow: str,
    user_id: str | None,
    session_id: str | None,
    user_product_id: int | None,
    input_mode: str | None,
    product_name: str | None,
    product_page_url: str | None,
    region_label: str | None,
    raw_ocr_text: str | None,
    extracted_ingredient_text: str | None,
    extracted_warning_text: str | None,
    inferred_product_use_category: str | None,
    inferred_material_subcategory: str | None,
    recommendation_bucket: str | None,
    review_reasons: list[str],
    review_notes: str | None,
    review_payload: dict[str, Any],
) -> int:
    priority = "high" if any(
        reason in review_reasons
        for reason in ["user_corrected_ocr_text", "user_corrected_category", "unknown_product_category"]
    ) else "normal"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO review_queue (
                source_flow,
                user_id,
                session_id,
                user_product_id,
                input_mode,
                product_name,
                product_page_url,
                region_label,
                raw_ocr_text,
                extracted_ingredient_text,
                extracted_warning_text,
                inferred_product_use_category,
                inferred_material_subcategory,
                recommendation_bucket,
                review_reasons,
                review_notes,
                review_payload,
                priority
            )
            VALUES (
                %(source_flow)s,
                %(user_id)s,
                %(session_id)s,
                %(user_product_id)s,
                %(input_mode)s,
                %(product_name)s,
                %(product_page_url)s,
                %(region_label)s,
                %(raw_ocr_text)s,
                %(extracted_ingredient_text)s,
                %(extracted_warning_text)s,
                %(inferred_product_use_category)s,
                %(inferred_material_subcategory)s,
                %(recommendation_bucket)s,
                %(review_reasons)s,
                %(review_notes)s,
                %(review_payload)s,
                %(priority)s
            )
            RETURNING review_id;
            """,
            {
                "source_flow": source_flow,
                "user_id": user_id,
                "session_id": session_id,
                "user_product_id": user_product_id,
                "input_mode": input_mode,
                "product_name": product_name,
                "product_page_url": product_page_url,
                "region_label": region_label,
                "raw_ocr_text": raw_ocr_text,
                "extracted_ingredient_text": extracted_ingredient_text,
                "extracted_warning_text": extracted_warning_text,
                "inferred_product_use_category": inferred_product_use_category,
                "inferred_material_subcategory": inferred_material_subcategory,
                "recommendation_bucket": recommendation_bucket,
                "review_reasons": json.dumps(review_reasons, ensure_ascii=False),
                "review_notes": review_notes,
                "review_payload": json.dumps(review_payload, ensure_ascii=False, default=str),
                "priority": priority,
            },
        )
        review_id = int(cur.fetchone()["review_id"])
    conn.commit()
    return review_id


def save_user_feedback(
    conn: psycopg.Connection[Any],
    *,
    review_id: int | None,
    user_id: str | None,
    session_id: str | None,
    product_name: str | None,
    input_mode: str | None,
    feedback_text: str,
    feedback_payload: dict[str, Any],
    owner_email: str = "wanru.adelie@gmail.com",
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_feedback (
                review_id,
                user_id,
                session_id,
                product_name,
                input_mode,
                feedback_text,
                owner_email,
                feedback_payload
            )
            VALUES (
                %(review_id)s,
                %(user_id)s,
                %(session_id)s,
                %(product_name)s,
                %(input_mode)s,
                %(feedback_text)s,
                %(owner_email)s,
                %(feedback_payload)s
            )
            RETURNING feedback_id;
            """,
            {
                "review_id": review_id,
                "user_id": user_id,
                "session_id": session_id,
                "product_name": product_name,
                "input_mode": input_mode,
                "feedback_text": feedback_text,
                "owner_email": owner_email,
                "feedback_payload": json.dumps(feedback_payload, ensure_ascii=False, default=str),
            },
        )
        feedback_id = int(cur.fetchone()["feedback_id"])
    conn.commit()
    return feedback_id


def maybe_notify_feedback_owner(
    conn: psycopg.Connection[Any],
    *,
    feedback_id: int,
    owner_email: str,
    product_name: str | None,
    feedback_text: str,
) -> None:
    smtp_host = normalize_text(os.getenv("HAZARDLY_SMTP_HOST"))
    smtp_port = int(os.getenv("HAZARDLY_SMTP_PORT", "587"))
    smtp_user = os.getenv("HAZARDLY_SMTP_USER", "")
    smtp_password = os.getenv("HAZARDLY_SMTP_PASSWORD", "")
    sender = os.getenv("HAZARDLY_FEEDBACK_FROM_EMAIL", smtp_user)
    if not all([smtp_host, smtp_user, smtp_password, sender]):
        return

    message = EmailMessage()
    message["Subject"] = f"Hazardly feedback #{feedback_id}"
    message["From"] = sender
    message["To"] = owner_email
    message.set_content(
        "\n".join(
            [
                "A Hazardly user submitted feedback.",
                f"Feedback ID: {feedback_id}",
                f"Product: {product_name or 'Unknown product'}",
                "",
                feedback_text,
            ]
        )
    )
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(message)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE user_feedback
                SET notification_status = 'sent',
                    notification_sent_at = NOW(),
                    notification_error = NULL
                WHERE feedback_id = %(feedback_id)s;
                """,
                {"feedback_id": feedback_id},
            )
        conn.commit()
    except Exception as exc:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE user_feedback
                SET notification_status = 'failed',
                    notification_error = %(notification_error)s
                WHERE feedback_id = %(feedback_id)s;
                """,
                {"feedback_id": feedback_id, "notification_error": str(exc)[:500]},
            )
        conn.commit()


def product_text_with_link_clues(product_text: str | None, product_page_url: str | None) -> str:
    text_parts = [product_text or ""]
    if product_page_url:
        parsed = urlparse(product_page_url.strip())
        host = parsed.netloc.replace("www.", " ").replace(".", " ")
        path = unquote(parsed.path)
        path = re.sub(r"[-_/]+", " ", path)
        path = re.sub(r"\s+", " ", path).strip()
        link_clues = " ".join(part for part in [host.strip(), path] if part)
        if link_clues:
            text_parts.append(link_clues)
    return " | ".join(part for part in text_parts if part).strip()


def save_user_product_analysis(
    conn: psycopg.Connection[Any],
    *,
    user_id: str,
    session_id: str | None,
    product_name: str | None,
    product_page_url: str | None,
    raw_ocr_text: str | None,
    extracted_ingredient_text: str | None,
    extracted_warning_text: str | None,
    region_label: str | None,
    product_matches: list[dict[str, Any]],
    category_info: dict[str, str],
    recommendation: dict[str, Any],
    concern_sources: list[dict[str, Any]],
    chemical_matches: list[dict[str, Any]],
    regulatory_evidence: list[dict[str, Any]],
    full_payload: dict[str, Any],
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_products (
                user_id,
                session_id,
                product_name,
                product_page_url,
                raw_ocr_text,
                extracted_ingredient_text,
                extracted_warning_text,
                region_label,
                matched_product_type_ids,
                matched_categories,
                recommendation_bucket,
                recommendation_summary,
                concern_sources,
                raw_analysis_payload
            )
            VALUES (
                %(user_id)s,
                %(session_id)s,
                %(product_name)s,
                %(product_page_url)s,
                %(raw_ocr_text)s,
                %(extracted_ingredient_text)s,
                %(extracted_warning_text)s,
                %(region_label)s,
                %(matched_product_type_ids)s,
                %(matched_categories)s,
                %(recommendation_bucket)s,
                %(recommendation_summary)s,
                %(concern_sources)s,
                %(raw_analysis_payload)s
            )
            RETURNING user_product_id;
            """,
            {
                "user_id": user_id,
                "session_id": session_id,
                "product_name": product_name,
                "product_page_url": product_page_url,
                "raw_ocr_text": raw_ocr_text,
                "extracted_ingredient_text": extracted_ingredient_text,
                "extracted_warning_text": extracted_warning_text,
                "region_label": region_label,
                "matched_product_type_ids": json.dumps([m.get("product_type_id") for m in product_matches if m.get("product_type_id")]),
                "matched_categories": json.dumps([category_info.get("product_use_category"), category_info.get("material_subcategory")]),
                "recommendation_bucket": recommendation.get("recommendation_bucket"),
                "recommendation_summary": recommendation.get("recommendation_reason"),
                "concern_sources": json.dumps(concern_sources, ensure_ascii=False, default=str),
                "raw_analysis_payload": json.dumps(full_payload, ensure_ascii=False, default=str),
            },
        )
        user_product_id = int(cur.fetchone()["user_product_id"])

        inserted_keys: set[tuple[str | None, str, str | None]] = set()
        for chem in chemical_matches:
            chem_id = chem.get("chemical_id")
            chem_name = chem.get("preferred_name") or chem.get("matched_text") or "unknown"
            relevant_rows = [row for row in regulatory_evidence if not chem_id or row.get("chemical_id") == chem_id]
            if not relevant_rows:
                relevant_rows = [{"source_authority": None, "country_or_jurisdiction": None, "regulatory_status": None, "hazard_basis": None}]
            for row in relevant_rows:
                key = (chem_id, chem_name, row.get("regulatory_status"))
                if key in inserted_keys:
                    continue
                inserted_keys.add(key)
                cur.execute(
                    """
                    INSERT INTO user_product_chemicals (
                        user_product_id,
                        chemical_id,
                        preferred_name,
                        source_authority,
                        country_or_jurisdiction,
                        regulatory_status,
                        hazard_basis,
                        matched_from
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        user_product_id,
                        chem_id,
                        chem_name,
                        row.get("source_authority"),
                        row.get("country_or_jurisdiction"),
                        row.get("regulatory_status"),
                        row.get("hazard_basis"),
                        chem.get("matched_text"),
                    ),
                )
    conn.commit()
    return user_product_id


def get_user_chemical_overlap(
    conn: psycopg.Connection[Any],
    *,
    user_id: str,
    chemical_ids: list[str],
) -> list[dict[str, Any]]:
    if not chemical_ids:
        return []
    sql = """
    SELECT
        upc.chemical_id,
        upc.preferred_name,
        COUNT(DISTINCT upc.user_product_id) AS product_count
    FROM user_product_chemicals upc
    JOIN user_products up ON up.user_product_id = upc.user_product_id
    WHERE up.user_id = %(user_id)s
      AND upc.chemical_id = ANY(%(chemical_ids)s)
    GROUP BY upc.chemical_id, upc.preferred_name
    ORDER BY product_count DESC, upc.preferred_name ASC;
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"user_id": user_id, "chemical_ids": chemical_ids})
        return list(cur.fetchall())


def analyze_product_for_app(
    conn: psycopg.Connection[Any],
    *,
    user_id: str | None,
    session_id: str | None,
    product_name: str | None,
    product_page_url: str | None,
    raw_ocr_text: str | None,
    ingredients_text: str | None,
    warning_text: str | None,
    region_label: str | None,
    input_mode: str | None = None,
    user_corrected_text: bool = False,
    user_corrected_category: bool = False,
    queue_for_review: bool = False,
    review_notes: str | None = None,
    save_to_history: bool = False,
) -> dict[str, Any]:
    product_text = product_text_with_link_clues(product_name, product_page_url)
    context = build_grounding_context(
        conn,
        product_text=product_name,
        product_page_url=product_page_url,
        ingredients_text=ingredients_text,
        warning_text=warning_text,
        region_label=region_label,
    )
    fetched_product_text = (context.get("url_context") or {}).get("product_text", "")
    fetched_ingredients_text = (context.get("url_context") or {}).get("ingredients_text", "")
    merged_product_for_category = " | ".join(
        part for part in [product_text, fetched_product_text] if normalize_text(part)
    )
    merged_ingredients_for_category = " | ".join(
        part for part in [ingredients_text or "", fetched_ingredients_text] if normalize_text(part)
    )
    category_info = infer_use_material(
        product_text=merged_product_for_category,
        ingredients_text=merged_ingredients_for_category,
        product_matches=context["product_matches"],
    )
    category_info = apply_product_label_category_hint(category_info, context.get("product_label_model", {}))
    recommendation_row = get_serving_recommendation(
        conn,
        product_use_category=category_info["product_use_category"],
        material_subcategory=category_info["material_subcategory"],
    )
    recommendation = derive_recommendation_bucket(
        regulatory_evidence=context["direct_regulatory_evidence"] or context["category_level_regulatory_evidence"],
        chemical_matches=context["chemical_matches"],
        recommendation_row=recommendation_row,
        warning_interpretations=context["warning_interpretations"],
        product_use_category=category_info["product_use_category"],
        material_subcategory=category_info["material_subcategory"],
        ingredients_text=ingredients_text,
        warning_text=warning_text,
    )
    has_direct_chemical_match = bool(context["chemical_matches"])
    concern_sources = summarize_concern_sources(context["direct_regulatory_evidence"])
    category_level_concern_sources = summarize_concern_sources(context["category_level_regulatory_evidence"])
    candidate_chemical_linkages = annotate_candidate_chemical_linkages(
        context.get("candidate_chemical_linkages", []),
        has_direct_chemical_match=has_direct_chemical_match,
    )
    context["candidate_chemical_linkages"] = candidate_chemical_linkages
    chemical_ids = [m["chemical_id"] for m in context["chemical_matches"] if m.get("chemical_id")]
    overlap = get_user_chemical_overlap(conn, user_id=user_id, chemical_ids=chemical_ids) if user_id else []
    evidence_scope_summary = {
        "has_direct_chemical_match": has_direct_chemical_match,
        "direct_chemical_match_count": len(context["chemical_matches"]),
        "has_direct_regulatory_evidence": bool(context["direct_regulatory_evidence"]),
        "direct_regulatory_evidence_count": len(context["direct_regulatory_evidence"]),
        "has_warning_text_signal": bool(context["warning_interpretations"]) or bool(normalize_text(warning_text)),
        "has_category_level_signal_only": (not has_direct_chemical_match) and bool(context["category_level_regulatory_evidence"]),
        "category_level_regulatory_evidence_count": len(context["category_level_regulatory_evidence"]),
        "has_candidate_product_chemical_linkage": bool(candidate_chemical_linkages),
        "candidate_product_chemical_linkage_count": len(candidate_chemical_linkages),
        "chemical_evidence_policy": (
            "Only direct chemical matches and direct regulatory evidence should be stated as product-specific. "
            "Category-level evidence and candidate linkages are hypotheses/context only."
        ),
    }
    intake_assessment = assess_input_sufficiency(
        input_mode=input_mode,
        product_name=product_name,
        product_page_url=product_page_url,
        raw_ocr_text=raw_ocr_text,
        ingredients_text=ingredients_text,
        warning_text=warning_text,
        url_context=context.get("url_context"),
    )

    result = {
        **context,
        "product_page_url": product_page_url,
        "inferred_category": category_info,
        "serving_recommendation": recommendation_row,
        "recommendation": recommendation,
        "concern_sources": concern_sources,
        "category_level_concern_sources": category_level_concern_sources,
        "evidence_scope_summary": evidence_scope_summary,
        "user_overlap_summary": overlap,
        "intake_assessment": intake_assessment,
        "input_mode": input_mode,
    }
    if risk_output_from_api_result is not None:
        try:
            result["structured_risk_output"] = risk_output_from_api_result(
                result,
                product_name=product_name or fetched_product_text,
                ingredients_text=merged_ingredients_for_category,
            )
        except Exception as exc:
            result["structured_risk_output_error"] = str(exc)
    try:
        from hazardly_score import hazardly_score_from_api_result

        score_input_text = " ".join(
            part for part in [
                raw_ocr_text or "",
                ingredients_text or "",
                fetched_ingredients_text or "",
                warning_text or "",
            ] if normalize_text(part)
        )
        score = hazardly_score_from_api_result(result, input_text=score_input_text)
        result["hazardly_score"] = {
            "score": score.score,
            "title": score.title,
            "description": score.description,
            "risk_signals": score.riskSignals,
            "is_food": score.isFood,
            "nutrition_flags": score.nutritionFlags,
            "flags": [flag.as_dict() for flag in score.flags],
            "total_risk_points": score.totalRiskPoints,
        }
    except Exception as exc:
        result["hazardly_score_error"] = str(exc)

    review_reasons = infer_review_reasons(
        category_info=category_info,
        recommendation=recommendation,
        evidence_scope_summary=evidence_scope_summary,
        user_corrected_text=user_corrected_text,
        user_corrected_category=user_corrected_category,
        raw_ocr_text=raw_ocr_text,
        product_name=product_name,
        ingredients_text=ingredients_text,
        warning_text=warning_text,
    )
    result["review_reasons"] = review_reasons

    user_product_id: int | None = None
    if save_to_history and user_id:
        user_product_id = save_user_product_analysis(
            conn,
            user_id=user_id,
            session_id=session_id,
            product_name=product_name,
            product_page_url=product_page_url,
            raw_ocr_text=raw_ocr_text,
            extracted_ingredient_text=ingredients_text,
            extracted_warning_text=warning_text,
            region_label=region_label,
            product_matches=context["product_matches"],
            category_info=category_info,
            recommendation=recommendation,
            concern_sources=concern_sources,
            chemical_matches=context["chemical_matches"],
            regulatory_evidence=context["regulatory_evidence"],
            full_payload=result,
        )
        result["saved_user_product_id"] = user_product_id
        result["user_overlap_summary"] = get_user_chemical_overlap(conn, user_id=user_id, chemical_ids=chemical_ids)

    if queue_for_review or review_reasons:
        review_id = enqueue_review_case(
            conn,
            source_flow="analyze_product_for_app",
            user_id=user_id,
            session_id=session_id,
            user_product_id=user_product_id,
            input_mode=input_mode,
            product_name=product_name,
            product_page_url=product_page_url,
            region_label=region_label,
            raw_ocr_text=raw_ocr_text,
            extracted_ingredient_text=ingredients_text,
            extracted_warning_text=warning_text,
            inferred_product_use_category=category_info.get("product_use_category"),
            inferred_material_subcategory=category_info.get("material_subcategory"),
            recommendation_bucket=recommendation.get("recommendation_bucket"),
            review_reasons=review_reasons,
            review_notes=review_notes,
            review_payload=result,
        )
        result["review_queue_id"] = review_id
        if queue_for_review and normalize_text(review_notes):
            feedback_id = save_user_feedback(
                conn,
                review_id=review_id,
                user_id=user_id,
                session_id=session_id,
                product_name=product_name,
                input_mode=input_mode,
                feedback_text=review_notes or "",
                feedback_payload=result,
            )
            result["user_feedback_id"] = feedback_id
            maybe_notify_feedback_owner(
                conn,
                feedback_id=feedback_id,
                owner_email="wanru.adelie@gmail.com",
                product_name=product_name,
                feedback_text=review_notes or "",
            )

    return result


def grounding_context_as_json(
    conn: psycopg.Connection[Any],
    *,
    product_text: str | None = None,
    product_page_url: str | None = None,
    ingredients_text: str | None = None,
    warning_text: str | None = None,
    region_label: str | None = None,
) -> str:
    payload = build_grounding_context(
        conn,
        product_text=product_text,
        product_page_url=product_page_url,
        ingredients_text=ingredients_text,
        warning_text=warning_text,
        region_label=region_label,
    )
    return json.dumps(payload, indent=2, ensure_ascii=False)
