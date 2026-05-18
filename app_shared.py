from __future__ import annotations

import json
import os
import re
import codecs
import subprocess
import tempfile
import uuid
from typing import Any
from urllib.parse import parse_qs, urlparse
from html import unescape

import requests

from vnext_contract import GroundedQueryEnvelope, NormalizedProductPayload, ReviewSignal, Stage2Decision


API_BASE_URL = os.getenv("GEMMA4GOOD_API_BASE_URL", "http://127.0.0.1:8010")
AMAZON_ASIN_RE = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:[/?]|$)", re.I)
AMAZON_BLOCK_RE = re.compile(
    r"(captcha|robot check|sorry, we just need to make sure|enter the characters you see below|"
    r"api-services-support@amazon|to discuss automated access|503 - service unavailable)",
    re.I,
)


def safe_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def merge_nonempty(*parts: str) -> str:
    return " | ".join(part for part in parts if safe_text(part))


def canonicalize_product_url(url: str) -> str:
    clean_url = safe_text(url)
    parsed = urlparse(clean_url)
    if "amazon." in parsed.netloc.lower():
        asin_match = AMAZON_ASIN_RE.search(parsed.path)
        if asin_match:
            return f"https://www.amazon.com/dp/{asin_match.group(1).upper()}"
        query = parse_qs(parsed.query)
        for key in ("pd_rd_i", "asin", "ASIN"):
            asin = safe_text((query.get(key) or [""])[0]).upper()
            if re.fullmatch(r"[A-Z0-9]{10}", asin):
                return f"https://www.amazon.com/dp/{asin}"
    return clean_url


def amazon_asin_from_url(url: str) -> str:
    parsed = urlparse(safe_text(url))
    if "amazon." not in parsed.netloc.lower():
        return ""
    asin_match = AMAZON_ASIN_RE.search(parsed.path)
    if asin_match:
        return asin_match.group(1).upper()
    query = parse_qs(parsed.query)
    for key in ("pd_rd_i", "asin", "ASIN"):
        asin = safe_text((query.get(key) or [""])[0]).upper()
        if re.fullmatch(r"[A-Z0-9]{10}", asin):
            return asin
    return ""


def amazon_fetch_candidates(url: str) -> list[str]:
    asin = amazon_asin_from_url(url)
    if not asin:
        return [url]
    return [
        f"https://www.amazon.com/dp/{asin}",
        f"https://www.amazon.com/gp/product/{asin}",
        f"https://www.amazon.com/gp/aw/d/{asin}",
    ]


def has_product_context(data: dict[str, Any]) -> bool:
    return any(
        safe_text(data.get(key))
        for key in [
            "product_name",
            "product_text",
            "ingredients",
            "ingredients_text",
            "materials",
            "nutrition_text",
            "nutrition_facts",
            "serving_size",
            "claims",
            "warnings",
            "warning_text",
            "safety_concerns",
        ]
    )


def looks_like_food_preview_context(data: dict[str, Any]) -> bool:
    blob = " ".join(
        safe_text(data.get(key))
        for key in ["product_name", "product_text", "category"]
    ).lower()
    if re.search(
        r"\b(water bottles?|drinkware|bottles?|tumblers?|hydration|tableware|cookware)\b",
        blob,
    ):
        return False
    return bool(
        re.search(
            r"\b(food|snack|cookie|biscuit|waffle|chips?|cracker|cereal|drink|beverage|tea|coffee|"
            r"kombucha|meat|sauce|candy|chocolate|bar|granola)\b",
            blob,
        )
    )


def looks_like_junk_product_context(data: dict[str, Any]) -> bool:
    detail_text = " ".join(
        safe_text(data.get(key)).lower()
        for key in [
            "ingredients",
            "ingredients_text",
            "materials",
            "claims",
            "warnings",
            "warning_text",
            "safety_concerns",
        ]
    )
    retail_noise = [
        "your views",
        "featured products",
        "guest ratings",
        "ratings & reviews",
        "disclaimer",
        "general disclaimer",
    ]
    relevant_detail = [
        "water",
        "sodium",
        "sulfate",
        "surfactant",
        "fragrance",
        "methylisothiazolinone",
        "benzisothiazolinone",
        "cotton",
        "polyester",
        "nylon",
        "spandex",
        "product warning",
        "caution",
    ]
    hard_stale_phrases = [
        "general disclaimer",
        "content on this site is for reference purposes only",
        "target does not represent or warrant",
        "we recommend that you do not rely solely",
    ]
    if any(phrase in detail_text for phrase in hard_stale_phrases):
        return True
    if any(phrase in detail_text for phrase in retail_noise) and not any(token in detail_text for token in relevant_detail):
        return True

    joined = " ".join(
        safe_text(data.get(key)).lower()
        for key in [
            "product_name",
            "product_text",
            "ingredients",
            "ingredients_text",
            "materials",
            "claims",
            "warnings",
            "warning_text",
            "safety_concerns",
            "error",
        ]
    )
    if not joined.strip():
        return True
    junk_phrases = [
        "https protocol",
        "technical documentation",
        "protocol standard",
        "amazon.com",
        "continue shopping",
        "access denied",
        "robot check",
        "captcha",
        "sorry, we just need to make sure",
        "not found",
        "your views",
        "featured products",
        "guest ratings",
        "disclaimer",
    ]
    useful_words = [
        "detergent",
        "waffle",
        "honey stinger",
        "peanut butter",
        "everspring",
        "shirt",
        "cotton",
        "polyester",
        "ingredients",
        "product warning",
    ]
    return any(phrase in joined for phrase in junk_phrases) and not any(word in joined for word in useful_words)


def normalize_preview_payload(url: str, raw_data: dict[str, Any], *, status: str, reason: str = "") -> dict[str, Any]:
    product_name = safe_text(raw_data.get("product_name"))
    product_text = safe_text(raw_data.get("product_text"))
    ingredients = safe_text(raw_data.get("ingredients")) or safe_text(raw_data.get("ingredients_text"))
    nutrition_text = safe_text(raw_data.get("nutrition_text")) or safe_text(raw_data.get("nutrition_facts"))
    warnings = safe_text(raw_data.get("warnings")) or safe_text(raw_data.get("warning_text"))
    claims = safe_text(raw_data.get("claims")) or safe_text(raw_data.get("safety_concerns"))
    materials = safe_text(raw_data.get("materials_text")) or safe_text(raw_data.get("materials"))
    ingredient_panel_text = safe_text(raw_data.get("ingredient_panel_text"))
    ingredient_panel_found = bool(raw_data.get("ingredient_panel_found")) or bool(ingredient_panel_text)
    has_data = has_product_context(raw_data)
    food_missing_ingredients = looks_like_food_preview_context(raw_data) and not ingredients and not materials
    can_proceed = has_data and not food_missing_ingredients
    if food_missing_ingredients:
        status = "needs_food_ingredients"
        if "amazon." in urlparse(url).netloc.lower():
            if ingredient_panel_found:
                reason = (
                    "I found the Amazon product page and an ingredient section, but Amazon only exposed an incomplete "
                    "ingredient snippet to the app. Please upload a clear photo of the full ingredient panel or paste "
                    "the ingredient text before analysis."
                )
            else:
                reason = (
                    "I found the Amazon product page, but Amazon did not expose a readable ingredient panel to the app. "
                    "Please upload a clear photo of the ingredient panel or paste the ingredient text before analysis."
                )
        else:
            reason = (
                "This appears to be a food product, but the webpage did not provide a readable ingredient list. "
                "Please upload a clear photo of the ingredient panel or paste the ingredient text before analysis."
            )
    elif not has_data:
        status = "needs_better_url"
        reason = (
            "I could not access enough readable product information from that webpage. "
            "Please paste the product name/description and the material or ingredient list, or upload product images instead."
        )
    return {
        "url_context": {
            "product_name": product_name or product_text,
            "product_text": product_text or product_name,
            "ingredients_text": ingredients,
            "materials_text": materials,
            "nutrition_text": nutrition_text,
            "serving_size": safe_text(raw_data.get("serving_size")),
            "warning_text": warnings or claims,
            "category": safe_text(raw_data.get("category")),
            "materials": materials,
            "safety_concerns": claims,
            "ingredient_panel_text": ingredient_panel_text,
            "ingredient_panel_found": ingredient_panel_found,
            "product_images": raw_data.get("product_images") if isinstance(raw_data.get("product_images"), list) else [],
            "processing_state": safe_text(raw_data.get("processing_state")),
            "processing_derivatives": safe_text(raw_data.get("processing_derivatives")),
            "concentration_assessment": safe_text(raw_data.get("concentration_assessment")),
            "is_from_search": bool(raw_data.get("is_from_search")),
            "normalized_url": canonicalize_product_url(url),
            "fetch_error": safe_text(raw_data.get("error")),
        },
        "intake_assessment": {
            "can_proceed": can_proceed,
            "status": status if has_data else "blocked/insufficient",
            "reason": "" if can_proceed else (reason or "Retailer blocked access and no usable product title, image, ingredients, material, or claims were found."),
            "recommended_next_step": (
                "Ready for analysis."
                if can_proceed
                else (
                    "Upload a clear ingredient-panel image or paste the ingredient text."
                    if food_missing_ingredients
                    else "Paste the product title/description in the same message, or upload product/package images."
                )
            ),
        },
    }


def clean_html_text(value: str) -> str:
    text = unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \n\t\r-:|")


def html_to_readable_text(value: str) -> str:
    html = unescape(value or "")
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    html = re.sub(
        r"(?i)</?(?:div|p|br|li|ul|ol|tr|td|th|table|section|article|h[1-6]|span|button)[^>]*>",
        "\n",
        html,
    )
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_amazon_ingredient_text(value: str) -> str:
    text = clean_html_text(value)
    text = re.sub(r"^(?:Active\s+)?Ingredients?\s*", "", text, flags=re.I).strip(" :.-")
    text = re.sub(r"^(?:Ingredient\s+Information|Important\s+Information)\s*", "", text, flags=re.I).strip(" :.-")
    text = re.sub(r"\.(?=Contains:)", ". ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if re.search(r"\b(function|var|window\.|document\.|placeholder|readystatechange)\b", text, re.I):
        return ""
    return text[:1200]


def decode_jsonish_text(value: str) -> str:
    text = value or ""
    try:
        text = json.loads(f'"{text}"')
    except Exception:
        try:
            text = codecs.decode(text, "unicode_escape")
        except Exception:
            pass
    return clean_html_text(text)


def is_plausible_ingredient_text(value: str) -> bool:
    text = clean_amazon_ingredient_text(value)
    if len(text) < 18:
        return False
    lowered = text.lower()
    if re.search(r"\b(customer|review|seller|shipping|delivery|privacy|cookie|javascript|advertising|sponsored)\b", lowered):
        return False
    if re.search(r"\b(product details|about this item|important information|directions|legal disclaimer)\b", lowered) and "," not in text:
        return False
    ingredient_clues = [
        ",",
        "contains:",
        "may contain",
        "water",
        "sugar",
        "flour",
        "oil",
        "salt",
        "milk",
        "soy",
        "cocoa",
        "lecithin",
        "fragrance",
        "surfactant",
        "glycerin",
        "sodium",
    ]
    return any(clue in lowered for clue in ingredient_clues)


def extract_ingredient_text_from_readable(text: str) -> str:
    readable = html_to_readable_text(text) if "<" in text else (text or "")
    readable = re.sub(r"\r", "\n", readable)
    lines = [line.strip(" \t:-") for line in readable.splitlines()]
    lines = [line for line in lines if line]
    stop_re = re.compile(
        r"^(?:directions|legal disclaimer|product description|about this item|from the manufacturer|"
        r"top highlights|item details|product details|nutrition facts|safety information|warning|warnings|"
        r"customers also|compare with|reviews?|videos?|important information)$",
        re.I,
    )
    label_re = re.compile(r"^(?:active\s+)?ingredients?$", re.I)
    inline_re = re.compile(r"^(?:active\s+)?ingredients?\s*[:：]\s*(.+)$", re.I)

    candidates: list[str] = []
    for index, line in enumerate(lines):
        inline = inline_re.match(line)
        if inline:
            candidates.append(inline.group(1))
            continue
        if not label_re.match(line):
            continue
        block: list[str] = []
        for following in lines[index + 1 : index + 12]:
            if stop_re.match(following):
                break
            if label_re.match(following):
                continue
            block.append(following)
            joined = " ".join(block)
            if len(joined) > 650:
                break
        if block:
            candidates.append(" ".join(block))

    for pattern in [
        r"(?:Active\s+)?Ingredients?\s*[:：]\s*(.{20,1200}?)(?:\n\s*(?:Directions|Legal Disclaimer|Product Description|About this item|Safety Information|Warnings?|Nutrition Facts)\b|$)",
        r"(?:Important Information).*?(?:Active\s+)?Ingredients?\s*[:：]?\s*(.{20,1200}?)(?:Directions|Legal Disclaimer|Product Description|About this item|Safety Information|Warnings?|$)",
    ]:
        for match in re.finditer(pattern, readable, re.I | re.S):
            candidates.append(match.group(1))

    for candidate in candidates:
        cleaned = clean_amazon_ingredient_text(candidate)
        if is_plausible_ingredient_text(cleaned):
            return cleaned[:1200]
    return ""


def extract_nutrition_text_from_readable(text: str) -> str:
    readable = html_to_readable_text(text) if "<" in text else (text or "")
    readable = re.sub(r"\r", "\n", readable)
    lines = [line.strip(" \t:-") for line in readable.splitlines()]
    lines = [line for line in lines if line]
    stop_re = re.compile(
        r"^(?:ingredients?|directions|legal disclaimer|product description|about this item|"
        r"safety information|warning|warnings|customers also|compare with|reviews?|videos?)$",
        re.I,
    )
    label_re = re.compile(r"^(?:nutrition\s+facts?|supplement\s+facts?)$", re.I)
    inline_re = re.compile(r"^(?:nutrition\s+facts?|supplement\s+facts?)\s*[:：]\s*(.+)$", re.I)

    candidates: list[str] = []
    for index, line in enumerate(lines):
        inline = inline_re.match(line)
        if inline:
            candidates.append(inline.group(1))
            continue
        if not label_re.match(line):
            continue
        block: list[str] = []
        for following in lines[index + 1 : index + 24]:
            if stop_re.match(following):
                break
            block.append(following)
            joined = " ".join(block)
            if len(joined) > 900:
                break
        if block:
            candidates.append(" ".join(block))

    for pattern in [
        r"(?:Nutrition\s+Facts?|Supplement\s+Facts?)\s*[:：]?\s*(.{30,1500}?)(?:\n\s*(?:Ingredients?|Directions|Warnings?|Legal Disclaimer)\b|$)",
        r"(?:serving\s+size|calories|total\s+fat|saturated\s+fat|sodium|total\s+sugars?|added\s+sugars?)\b(.{30,1200}?)(?:\n\s*(?:Ingredients?|Directions|Warnings?|Legal Disclaimer)\b|$)",
    ]:
        for match in re.finditer(pattern, readable, re.I | re.S):
            candidates.append(match.group(0))

    nutrition_terms = [
        r"\bserving\s+size\b",
        r"\bcalories?\b",
        r"\btotal\s+fat\b",
        r"\bsaturated\s+fat\b",
        r"\bsodium\b",
        r"\btotal\s+carbohydrates?\b",
        r"\btotal\s+sugars?\b",
        r"\badded\s+sugars?\b",
        r"\bprotein\b",
        r"%\s*dv\b",
    ]
    for candidate in candidates:
        cleaned = clean_html_text(candidate)
        if len(cleaned) < 25:
            continue
        if sum(1 for term in nutrition_terms if re.search(term, cleaned, re.I)) >= 3:
            return cleaned[:1200]
    return ""


def nutrition_dict_to_text(nutrition: dict[str, Any]) -> str:
    if not isinstance(nutrition, dict):
        return ""
    parts: list[str] = []
    for key, value in nutrition.items():
        if key in {"ingredients", "warning"}:
            continue
        if isinstance(value, (str, int, float)) and safe_text(str(value)):
            label = re.sub(r"[_-]+", " ", key).strip().title()
            parts.append(f"{label}: {value}")
        elif isinstance(value, dict):
            nested = nutrition_dict_to_text(value)
            if nested:
                parts.append(nested)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    nested = nutrition_dict_to_text(item)
                    if nested:
                        parts.append(nested)
                elif safe_text(str(item)):
                    parts.append(str(item))
    return " | ".join(dict.fromkeys(parts))[:1200]


def extract_serving_size(text: str) -> str:
    match = re.search(r"(?i)\bserv(?:ing)?\.?\s*size\s*[:：]?\s*([^|;\n]{1,80})", text or "")
    return clean_html_text(match.group(1)) if match else ""


def extract_amazon_json_ingredients(html: str) -> str:
    candidates: list[str] = []
    key_pattern = re.compile(
        r'"(?:ingredients?|ingredientStatement|ingredientText|ingredientsText|ingredient_list|ingredientList)"\s*:\s*"((?:\\.|[^"\\]){18,2200})"',
        re.I | re.S,
    )
    for match in key_pattern.finditer(html or ""):
        candidates.append(decode_jsonish_text(match.group(1)))

    # Amazon sometimes ships escaped HTML or JSON in data attributes/scripts.
    for match in re.finditer(r"(?:Ingredients?|INGREDIENTS?)\\?[:：]\\?\s*((?:\\.|[^<>{}\[\]]){20,1400})", html or "", re.I):
        candidates.append(decode_jsonish_text(match.group(1)))

    for candidate in candidates:
        cleaned = clean_amazon_ingredient_text(candidate)
        if is_plausible_ingredient_text(cleaned):
            return cleaned[:1200]
    return ""


def extract_meta_content(html: str, attr_name: str, attr_value: str) -> str:
    patterns = [
        rf'<meta[^>]+{attr_name}=["\']{re.escape(attr_value)}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+content=["\'](.*?)["\'][^>]+{attr_name}=["\']{re.escape(attr_value)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.I | re.S)
        if match:
            text = clean_html_text(match.group(1))
            if text:
                return text
    return ""


def split_short_claims(text: str) -> str:
    claims: list[str] = []
    for line in re.split(r"[\n;]+", clean_html_text(text)):
        clean = line.strip(" .;-")
        if not clean:
            continue
        if re.search(r"\b(var|function|return|placeholder|readystatechange|plugin|document\.|window\.)\b", clean, re.I):
            continue
        if len(clean) > 180:
            clean = clean[:177].rstrip() + "..."
        if clean not in claims:
            claims.append(clean)
    return "\n".join(f"- {claim}" for claim in claims[:6])


def extract_amazon_claims(html: str) -> str:
    sections: list[str] = []
    for section_id in ("pqv-feature-bullets", "featurebullets_feature_div"):
        section_match = re.search(
            rf'<div[^>]+id=["\']{section_id}["\'][^>]*>(.*?)(?:<div[^>]+id=["\']pqv-description["\']|<div[^>]+id=["\']productDescription|<div[^>]+id=["\']importantInformation|</ul>\s*</div>)',
            html,
            re.I | re.S,
        )
        if section_match:
            sections.append(section_match.group(1))

    bullets: list[str] = []
    for section in sections:
        for match in re.finditer(r'<li[^>]*>\s*<span[^>]*class=["\']a-list-item["\'][^>]*>(.*?)</span>\s*</li>', section, re.I | re.S):
            text = clean_html_text(match.group(1))
            if text and text not in bullets:
                bullets.append(text)
        if bullets:
            break
    return split_short_claims("\n".join(bullets))


def extract_amazon_ingredients(html: str) -> str:
    json_ingredients = extract_amazon_json_ingredients(html)
    if json_ingredients:
        return json_ingredients

    patterns = [
        r'<span[^>]*class=["\']a-text-bold["\'][^>]*>\s*Ingredients\s*</span>\s*<p>\s*<p>(.*?)</p>\s*</p>',
        r'<span[^>]*>\s*Ingredients\s*</span>\s*<p>\s*<p>(.*?)</p>\s*</p>',
        r'<span[^>]*class=["\']a-text-bold["\'][^>]*>\s*Ingredients\s*</span>\s*(.*?)(?:<span[^>]*class=["\']a-text-bold["\']|</div>\s*</div>|<h2>|$)',
        r'(?:Important Information|Safety Information).*?(?:Ingredients|Ingredient)\s*(.*?)(?:Directions|Legal Disclaimer|Product Description|About this item|$)',
        r'(?:Materials\s*&\s*Care|Product details).*?(?:Active\s+Ingredients|Ingredients|Ingredient)\s*(.*?)(?:Additional details|Directions|Safety Information|Legal Disclaimer|Product Description|About this item|$)',
        r'(?:Active\s+Ingredients|Ingredients|Ingredient)\s*[:：]?\s*(.*?)(?:\.\s+[A-Z][a-z]+:|Directions|Legal Disclaimer|Additional details|Safety Information|Product Description|About this item|$)',
        r'(?:Product Description|About this item).*?(?:Active\s+Ingredients|Ingredients|Ingredient)\s*[:：]?\s*(.*?)(?:Directions|Legal Disclaimer|$)',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.I | re.S)
        if not match:
            continue
        text = clean_amazon_ingredient_text(match.group(1))
        if is_plausible_ingredient_text(text):
            return text[:900]
    return extract_ingredient_text_from_readable(html)[:900]


def extract_amazon_ingredient_panel_snippet(html: str) -> str:
    readable = html_to_readable_text(html)
    for pattern in [
        r"(?is)\bingredients?\b\s*(.{1,320}?)(?:\btop highlights\b|\bitem details\b|\bfeatures?\s*&\s*specs\b|\blegal disclaimer\b|$)",
        r"(?is)\bimportant information\b.*?\bingredients?\b\s*(.{1,320}?)(?:\blegal disclaimer\b|$)",
    ]:
        match = re.search(pattern, readable)
        if match:
            snippet = clean_amazon_ingredient_text(match.group(1))
            if snippet:
                return snippet[:320]
    return ""


def extract_amazon_nutrition(html: str) -> str:
    for pattern in [
        r'"(?:nutritionFacts|nutrition_facts|nutritionInfo|nutrition_info)"\s*:\s*"((?:\\.|[^"\\]){30,2200})"',
        r"(?:Nutrition\s+Facts?|Supplement\s+Facts?)\s*[:：]?\s*(.{30,1800}?)(?:Ingredients|Directions|Legal Disclaimer|Product Description|About this item|$)",
    ]:
        for match in re.finditer(pattern, html or "", re.I | re.S):
            candidate = decode_jsonish_text(match.group(1))
            nutrition = extract_nutrition_text_from_readable(candidate)
            if nutrition:
                return nutrition
    return extract_nutrition_text_from_readable(html)[:1200]


def infer_retail_category_from_text(text: str) -> str:
    normalized = safe_text(text).lower()
    if re.search(r"\b(conditioner|shampoo|body wash|lotion|serum|moisturizer|deodorant|hair|skin care|beauty)\b", normalized):
        return "Personal Care"
    if re.search(r"\b(detergent|cleaner|disinfect|degreaser|laundry|dish soap)\b", normalized):
        return "Household Cleaner"
    if re.search(r"\b(waffle|bar|protein|coffee|tea|snack|cereal|granola|food|drink|beverage|meat|duck|chicken|beef)\b", normalized):
        return "Food"
    return ""


def iter_nested_values(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from iter_nested_values(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_nested_values(item)


def split_target_warnings(text: str) -> str:
    raw = clean_html_text(text)
    raw = re.sub(
        r"\s+(CAUTION|Contains|FIRST AID TREATMENT|Contains fragrance allergens)\s*:",
        r"\n\1:",
        raw,
        flags=re.I,
    )
    lines: list[str] = []
    for part in re.split(r"[\n;]+", raw):
        clean = part.strip(" .;:-,\t")
        if not clean:
            continue
        if len(clean) > 220:
            clean = clean[:217].rstrip() + "..."
        if clean not in lines:
            lines.append(clean)
    return "\n".join(f"- {line}" for line in lines[:8])


def extract_target_json_context(html: str, url: str) -> dict[str, Any]:
    if "target.com" not in urlparse(url).netloc.lower():
        return {}

    result: dict[str, Any] = {
        "product_name": "",
        "product_text": "",
        "category": "",
        "ingredients_text": "",
        "nutrition_text": "",
        "serving_size": "",
        "warning_text": "",
    }
    for match in re.finditer(r"JSON\.parse\(\"(.*?)\"\)", html, re.S):
        try:
            decoded = codecs.decode(match.group(1), "unicode_escape")
            blob = json.loads(decoded)
        except Exception:
            continue

        for node in iter_nested_values(blob):
            if not isinstance(node, dict):
                continue
            nutrition = node.get("nutrition_facts")
            if isinstance(nutrition, dict):
                ingredients = clean_html_text(nutrition.get("ingredients", ""))
                ingredients = re.sub(r"\s*\(Parenthesis State Source of Ingredient\)\.?\s*$", "", ingredients, flags=re.I)
                warning = split_target_warnings(nutrition.get("warning", ""))
                if ingredients:
                    result["ingredients_text"] = ingredients[:700]
                nutrition_text = nutrition_dict_to_text(nutrition)
                if nutrition_text:
                    result["nutrition_text"] = nutrition_text
                    result["serving_size"] = extract_serving_size(nutrition_text)
                if warning:
                    result["warning_text"] = warning

            category = node.get("category")
            if isinstance(category, dict) and category.get("name"):
                result["category"] = clean_html_text(category.get("name"))

            product_description = node.get("product_description")
            if isinstance(product_description, dict):
                title = clean_html_text(product_description.get("title", ""))
                if title:
                    result["product_name"] = title
                    result["product_text"] = title

            if result["product_text"] and result["ingredients_text"] and result["nutrition_text"] and result["warning_text"]:
                return result
    return result


def fetch_html(url: str, headers: dict[str, str]) -> str:
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


def extract_amazon_context(html: str) -> dict[str, Any]:
    if AMAZON_BLOCK_RE.search(html):
        return {"error": "Amazon returned a bot-block or service-unavailable page."}

    title = ""
    for pattern in [
        r'<span[^>]+id=["\']productTitle["\'][^>]*>(.*?)</span>',
        r'<meta[^>]+name=["\']title["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']',
        r"<title>(.*?)</title>",
    ]:
        match = re.search(pattern, html, re.I | re.S)
        if match:
            title = clean_html_text(match.group(1))
            break

    title = re.sub(r"^Amazon\.com\s*:\s*", "", title, flags=re.I)
    title = re.sub(r"\s*:\s*Health\s*&\s*Household.*$", "", title, flags=re.I)
    title = re.sub(r"\s*:\s*Breakfast Energy And Nutritional Bars.*$", "", title, flags=re.I)
    title = title.strip(" :-|")
    claims = extract_amazon_claims(html)
    ingredients = extract_amazon_ingredients(html)
    ingredient_panel_text = extract_amazon_ingredient_panel_snippet(html)
    nutrition_text = extract_amazon_nutrition(html)
    if not title and not claims and not ingredients:
        return {"error": "Amazon page was fetched, but no product title or product bullets were readable."}
    return {
        "product_name": title,
        "product_text": title,
        "ingredients_text": ingredients,
        "ingredient_panel_found": bool(ingredient_panel_text),
        "ingredient_panel_text": ingredient_panel_text,
        "nutrition_text": nutrition_text,
        "serving_size": extract_serving_size(nutrition_text),
        "claims": claims,
        "category": infer_retail_category_from_text(title),
    }


def direct_fetch_product_context(url: str) -> dict[str, Any]:
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
    if "amazon." in urlparse(url).netloc.lower():
        errors: list[str] = []
        best_partial: dict[str, Any] = {}
        for candidate_url in amazon_fetch_candidates(url):
            try:
                html = fetch_html(candidate_url, headers)
                data = extract_amazon_context(html)
                if has_product_context(data) and not looks_like_junk_product_context(data):
                    if safe_text(data.get("ingredients_text")) or safe_text(data.get("ingredients")):
                        return data
                    if not best_partial:
                        best_partial = data
                    errors.append(f"{candidate_url}: product found but ingredients dropdown was not extracted")
                    continue
                if data.get("error"):
                    errors.append(f"{candidate_url}: {data['error']}")
            except Exception as exc:
                errors.append(f"{candidate_url}: {exc}")
        if best_partial:
            return best_partial
        raise RuntimeError(" | ".join(errors) or "Amazon fetch attempts returned no usable context.")

    html = fetch_html(url, headers)
    target_data = extract_target_json_context(html, url)
    if has_product_context(target_data) and not looks_like_junk_product_context(target_data):
        return target_data

    title = (
        extract_meta_content(html, "property", "og:title")
        or extract_meta_content(html, "name", "twitter:title")
    )
    desc = (
        extract_meta_content(html, "property", "og:description")
        or extract_meta_content(html, "name", "description")
    )
    nutrition_text = extract_nutrition_text_from_readable(html)
    return {
        "product_name": title,
        "product_text": " | ".join(part for part in [title, desc] if safe_text(part)),
        "nutrition_text": nutrition_text,
        "serving_size": extract_serving_size(nutrition_text),
    }


def has_amazon_ingredients_gap(url: str, data: dict[str, Any]) -> bool:
    return (
        "amazon." in urlparse(url).netloc.lower()
        and has_product_context(data)
        and not safe_text(data.get("ingredients"))
        and not safe_text(data.get("ingredients_text"))
    )


def retailer_blocked_or_unreadable(data: dict[str, Any]) -> bool:
    text = " ".join(
        safe_text(data.get(key))
        for key in ["error", "fetch_error", "product_text", "raw_text_dump"]
    ).lower()
    return bool(data.get("is_blocked")) or any(
        marker in text
        for marker in [
            "robot check",
            "captcha",
            "access denied",
            "continue shopping",
            "503 - service unavailable",
            "retailer block",
        ]
    )


def ensure_stage2_decision(structured_data: dict[str, Any]) -> Stage2Decision:
    return Stage2Decision(
        product_use_category=safe_text(structured_data.get("product_use_category")) or "unknown",
        material_or_form=safe_text(structured_data.get("material_or_form")) or "unknown",
        information_priority=safe_text(structured_data.get("information_priority")) or "material_first",
        confidence_notes=safe_text(structured_data.get("confidence_notes")),
    )


def build_envelope(
    *,
    user_id: str,
    region: str,
    product_page_url: str,
    raw_ocr_text: str,
    structured_data: dict[str, Any],
    input_mode: str,
    user_question: str = "",
    user_corrected_text: bool = False,
    user_corrected_category: bool = False,
    queue_for_review: bool = False,
    review_notes: str = "",
) -> GroundedQueryEnvelope:
    normalized = NormalizedProductPayload(
        product_name=safe_text(structured_data.get("product_name")),
        product_page_url=safe_text(product_page_url),
        raw_ocr_text=safe_text(raw_ocr_text),
        ingredient_text=safe_text(structured_data.get("ingredient_text")),
        nutrition_text=safe_text(structured_data.get("nutrition_text")) or safe_text(structured_data.get("nutrition_facts")),
        material_text=safe_text(structured_data.get("material_text")),
        processing_method=safe_text(structured_data.get("processing_method")) or safe_text(structured_data.get("processing_state")),
        packaging_material=safe_text(structured_data.get("packaging_material")),
        processing_derivatives=safe_text(structured_data.get("processing_derivatives")),
        concentration_assessment=safe_text(structured_data.get("concentration_assessment")),
        warning_text=safe_text(structured_data.get("warning_text")),
        safety_caution_text=safe_text(structured_data.get("safety_caution_text")),
        category_clues=merge_nonempty(
            safe_text(structured_data.get("category_clues")),
            safe_text(structured_data.get("reasoning")),
        ),
        region=safe_text(region) or "California, USA",
        input_mode=safe_text(input_mode) or "image",
        user_question=safe_text(user_question),
    )
    review = ReviewSignal(
        user_corrected_text=user_corrected_text,
        user_corrected_category=user_corrected_category,
        queue_for_review=queue_for_review,
        review_notes=safe_text(review_notes),
    )
    return GroundedQueryEnvelope(
        user_id=safe_text(user_id) or "local_demo_user",
        session_id=str(uuid.uuid4()),
        payload=normalized,
        stage2=ensure_stage2_decision(structured_data),
        review=review,
    )


def call_local_api(payload: dict[str, Any]) -> dict[str, Any]:
    # Balanced 180s timeout for complex local VLM + RAG tasks
    response = requests.post(f"{API_BASE_URL}/analyze-product", json=payload, timeout=180)
    response.raise_for_status()
    return response.json()


RISKLENS_LOGIC_VERSION = "26.15"


def preview_url(url: str, region: str = "California, USA") -> dict[str, Any]:
    url = canonicalize_product_url(url)
    from database_manager import ProductDatabase
    db = ProductDatabase()

    # 1. Check local database cache first
    cached_data = db.get_product(url)
    is_stale = False
    if cached_data:
        # Refresh only caches that need newer extraction logic. A complete,
        # usable cached product should not become slow again just because the
        # extractor version changed.
        cached_version = cached_data.get("logic_version", "1.0")
        version_mismatch = cached_version != RISKLENS_LOGIC_VERSION

        # Strengthened junk detection
        name = cached_data.get("product_name", "").lower()
        text = cached_data.get("product_text", "").lower()
        junk_triggers = ["amazon.com", "continue shopping", "https", "wikipedia", "protocol", "access denied"]
        
        if any(k in name for k in junk_triggers) or any(k in text for k in ["robot", "captcha"]):
            # Double check it's not a valid product name that coincidentally matches (unlikely for Wikipedia/Protocol)
            if not any(p in name for p in ["detergent", "cookie", "everspring"]):
                is_stale = True
                print(f"Junk detected in cache for {url}, forcing fresh fetch.")
        if not has_product_context(cached_data) or looks_like_junk_product_context(cached_data):
            is_stale = True
            print(f"Insufficient or junk cached URL context for {url}, forcing fresh fetch.")
        if (
            "amazon." in urlparse(url).netloc.lower()
            and version_mismatch
            and not safe_text(cached_data.get("ingredients"))
            and not safe_text(cached_data.get("ingredients_text"))
        ):
            is_stale = True
            print(f"Amazon cache for {url} has no ingredients under old logic, forcing one refresh.")
        elif version_mismatch and not is_stale:
            print(
                f"Cache for {url} uses older logic version {cached_version}, "
                f"but it already has usable product context. Reusing cache."
            )
        
        if not is_stale:
            return normalize_preview_payload(url, cached_data, status="success (from local database)")

    # 2. Try local API
    try:
        response = requests.post(
            f"{API_BASE_URL}/preview-url",
            json={"product_page_url": safe_text(url), "region": safe_text(region) or "California, USA"},
            timeout=60, # Increased for mobile hotspots
        )
        if response.ok:
            api_result = response.json()
            if api_result.get("intake_assessment", {}).get("can_proceed", False) or has_product_context(api_result.get("url_context", {})):
                api_context = api_result.get("url_context", {})
                if looks_like_junk_product_context(api_context):
                    print(f"Junk detected in API URL preview for {url}, trying direct extractor.")
                elif has_amazon_ingredients_gap(url, api_context):
                    print(f"Amazon API preview for {url} has no ingredients, trying direct extractor.")
                else:
                    db.save_product(url, api_context, logic_version=RISKLENS_LOGIC_VERSION)
                    return api_result
    except Exception:
        pass

    raw_data: dict[str, Any] = {}

    # 3. Direct code-based fetch/extraction. This is intentionally deterministic:
    # Gemma should clean already-extracted fields, not fetch or interpret raw pages.
    try:
        direct_data = direct_fetch_product_context(url)
        if has_product_context(direct_data):
            if has_amazon_ingredients_gap(url, direct_data):
                raw_data = direct_data
                print(f"Direct Amazon fetch for {url} found product context but no ingredients; trying browser dropdown extraction.")
            else:
                db.save_product(url, direct_data, logic_version=RISKLENS_LOGIC_VERSION)
                return normalize_preview_payload(url, direct_data, status="success (direct extractor)")
    except Exception as exc:
        print(f"Direct extractor failed: {exc}")

    # 4. Optional local BrowserFetcher fallback
    if os.getenv("GEMMA4GOOD_ENABLE_BROWSER_FETCH", "1") == "1":
        try:
            from browser_fetcher import BrowserFetcher
            fetcher = BrowserFetcher(headless=True)
            browser_data = fetcher.fetch(url)
            if has_product_context(browser_data):
                raw_data = {
                    **raw_data,
                    **{key: value for key, value in browser_data.items() if safe_text(value) or isinstance(value, list)},
                }
                if has_amazon_ingredients_gap(url, raw_data) is False and "amazon." in urlparse(url).netloc.lower():
                    db.save_product(url, raw_data, logic_version=RISKLENS_LOGIC_VERSION)
                    return normalize_preview_payload(url, raw_data, status="success (browser dropdown extractor)")
            
            # v26.3: Process discovered images (e.g. SayWeee ingredient labels)
            if raw_data.get("product_images") and not retailer_blocked_or_unreadable(raw_data):
                print(f"Found {len(raw_data['product_images'])} potential labels. Downloading for visual scan...")
                img_paths = []
                for i, img_url in enumerate(raw_data["product_images"][:3]):
                    try:
                        img_res = requests.get(img_url, timeout=10)
                        if img_res.ok:
                            temp_path = f"outputs/temp_inputs/web_label_{i}.png"
                            os.makedirs("outputs/temp_inputs", exist_ok=True)
                            with open(temp_path, "wb") as f:
                                f.write(img_res.content)
                            img_paths.append(temp_path)
                    except: continue
                
                if img_paths:
                    print("Running deep visual scan on web images...")
                    from mlx_engine import run_scribe_agent
                    web_ocr = run_scribe_agent(img_paths)
                    # Combine web OCR with text data
                    raw_data["ingredients"] = merge_nonempty(raw_data.get("ingredients", ""), web_ocr)
                    raw_data["had_visual_scan"] = True

        except Exception as exc:
            print(f"BrowserFetcher crashed: {exc}")
            raw_data = {"is_blocked": True, "error": str(exc)}

    # 5. Optional web search fallback. Disabled by default because the search
    # package can crash in local desktop environments without keychain access.
    if os.getenv("GEMMA4GOOD_ENABLE_WEB_SEARCH") == "1" and (
        raw_data.get("is_blocked") or not has_product_context(raw_data)
    ):
        try:
            from search_fetcher import SearchFetcher
            sf = SearchFetcher()
            search_data = sf.search_product(url)
            if search_data.get("found"):
                print("Using Search Fallback data.")
                # Merge search data into raw_data structure
                raw_data["product_name"] = search_data.get("product_name") or raw_data.get("product_name")
                raw_data["product_text"] = search_data.get("product_text")
                raw_data["ingredients"] = search_data.get("ingredients")
                raw_data["is_blocked"] = False # Search unblocked us
                raw_data["is_from_search"] = True
        except Exception as se:
            print(f"Search fallback also failed: {se}")

    # Save to local database if we found anything useful
    if has_product_context(raw_data):
        db.save_product(url, raw_data, logic_version=RISKLENS_LOGIC_VERSION)
    status = "success (search fallback)" if raw_data.get("is_from_search") else "success (browser fallback)"
    return normalize_preview_payload(
        url,
        raw_data,
        status=status,
        reason=(
            "I could not extract a usable product title, ingredients/materials, or claims from this URL. "
            "For Amazon/Target this often means the retailer blocked direct scraping; paste the product title/details "
            "or attach product/package images in the same chat message."
        ),
    )


def check_local_api() -> tuple[bool, str]:
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - UI path
        return False, str(exc)
    return True, "ok"


def calculate_risklens_score(api_result: dict[str, Any]) -> str:
    """Compatibility wrapper for the UI RiskLens Score calculation."""
    from risklens_score import risklens_score_from_api_result

    return risklens_score_from_api_result(api_result).score


def dump_debug_json(
    *,
    envelope: GroundedQueryEnvelope,
    structured_data: dict[str, Any],
    api_result: dict[str, Any],
    provider: str,
    raw_ocr_text: str,
) -> str:
    payload = {
        "provider": provider,
        "raw_ocr_text": raw_ocr_text,
        "structured_ocr": structured_data,
        "envelope": {
            "user_id": envelope.user_id,
            "session_id": envelope.session_id,
            "payload": envelope.payload.as_dict(),
            "stage2": envelope.stage2.as_dict(),
            "review": envelope.review.as_dict(),
            "api_payload": envelope.as_api_payload(),
        },
        "api_result": api_result,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
