from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any, Literal


HazardlyGrade = Literal["A", "B", "C", "D", "E"]


GRADE_META: dict[HazardlyGrade, dict[str, str]] = {
    "A": {
        "label": "Low concern",
        "color": "#1f9d55",
        "description": (
            "Low concern: No major risky ingredients, materials, contaminants, additives, "
            "or warning signals were found from supported sources."
        ),
    },
    "B": {
        "label": "Mild concern",
        "color": "#78c850",
        "description": (
            "Mild concern: Some minor caution signals may exist, but likely exposure is low under normal use."
        ),
    },
    "C": {
        "label": "Moderate concern",
        "color": "#f2cf3a",
        "description": (
            "Moderate concern: This product contains or may involve signals that deserve caution, "
            "especially with frequent use or exposure."
        ),
    },
    "D": {
        "label": "High concern",
        "color": "#f28c28",
        "description": (
            "High concern: This product contains or may involve substances with stronger warning signals "
            "from supported sources. Consider reducing frequent use or choosing alternatives with fewer flagged ingredients."
        ),
    },
    "E": {
        "label": "Very high concern",
        "color": "#d64545",
        "description": (
            "Very high concern: This product has prominent or high-exposure risk signals. "
            "Avoid frequent use and consider safer alternatives."
        ),
    },
}


NUTRITION_FLAG_OPTIONS = {
    "High added sugar",
    "High sugar",
    "High sodium",
    "High saturated fat",
    "Ultra-processed",
    "Common allergens",
}


@dataclass
class HazardlyScoreBar:
    score: HazardlyGrade
    title: str = "Hazardly Score"
    description: str = ""
    riskSignals: list[str] = field(default_factory=list)
    isFood: bool = False
    nutritionFlags: list[str] = field(default_factory=list)

    def to_html(self) -> str:
        score = normalize_score(self.score)
        description = self.description or GRADE_META[score]["description"]
        risk_items = "".join(
            f"<li>{html.escape(signal)}</li>"
            for signal in self.riskSignals[:5]
            if signal.strip()
        )
        risk_block = (
            f"<div class='hz-risk-signals'><div class='hz-subtitle'>Key risk signals</div><ul>{risk_items}</ul></div>"
            if risk_items
            else ""
        )
        food_flags = [flag for flag in self.nutritionFlags if flag in NUTRITION_FLAG_OPTIONS]
        flags = "".join(f"<span class='hz-food-flag'>{html.escape(flag)}</span>" for flag in food_flags)
        food_block = (
            "<div class='hz-food-flags'>"
            "<div class='hz-subtitle'>Food flags</div>"
            f"<div class='hz-food-flag-row'>{flags}</div>"
            "<div class='hz-footnote'>These food-only flags do not affect the A-E Hazardly Score.</div>"
            "</div>"
            if self.isFood and flags
            else ""
        )
        segments = "".join(_segment_html(grade, selected=(grade == score)) for grade in ["A", "B", "C", "D", "E"])
        return f"""
<section class="hazardly-score-card" aria-label="{html.escape(self.title)}">
  <style>
    @font-face {{
      font-display: swap;
      font-family: "ReferoBase";
      font-style: normal;
      font-weight: 300 900;
      src: url("https://refero.design/static/media/base-variable.7a7678ae49a8b605a15b.woff2") format("woff2");
    }}
    .hazardly-score-card {{
      --hz-border: rgba(12, 41, 126, 0.12);
      --hz-soft-border: rgba(12, 41, 126, 0.071);
      --hz-text: #13151b;
      --hz-muted: rgba(3, 14, 49, 0.55);
      --hz-card: rgba(247, 248, 251, 0.78);
      --hz-chip: rgba(238, 240, 246, 0.9);
      border: 1px solid var(--hz-border);
      border-radius: 32px;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(247, 248, 251, 0.72)),
        var(--hz-card);
      box-shadow:
        0 1px 3px rgba(12, 41, 126, 0.09),
        0 0 1px 0.4px rgba(12, 41, 126, 0.05),
        inset 0 0 0 1px rgba(255, 255, 255, 0.72);
      padding: 20px 20px 18px;
      margin: 12px 0 18px;
      color: var(--hz-text);
      font-family: "ReferoBase", -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif;
      letter-spacing: -0.02em;
      backdrop-filter: blur(18px);
    }}
    .hz-header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      margin-bottom: 16px;
    }}
    .hz-title {{
      font-size: 18px;
      font-weight: 760;
      letter-spacing: -0.045em;
    }}
    .hz-grade-pill {{
      border-radius: 999px;
      background: rgba(238, 240, 246, 0.95);
      color: rgba(19, 21, 27, 0.78);
      border: 1px solid var(--hz-soft-border);
      font-size: 13px;
      font-weight: 680;
      letter-spacing: -0.02em;
      padding: 7px 12px;
      box-shadow: none;
      white-space: nowrap;
    }}
    .hz-bar {{
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      border-radius: 20px;
      overflow: visible;
      gap: 2px;
      min-height: 46px;
      position: relative;
      padding: 3px;
      background: rgba(255, 255, 255, 0.76);
      border: 1px solid var(--hz-soft-border);
    }}
    .hz-segment {{
      position: relative;
      min-height: 44px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-weight: 760;
      text-shadow: 0 1px 2px rgba(0,0,0,0.22);
      border-top: 1px solid rgba(255,255,255,0.55);
      border-bottom: 1px solid rgba(0,0,0,0.08);
    }}
    .hz-segment:first-child {{ border-radius: 16px 8px 8px 16px; }}
    .hz-segment:last-child {{ border-radius: 8px 16px 16px 8px; }}
    .hz-segment:not(:first-child):not(:last-child) {{ border-radius: 8px; }}
    .hz-segment.hz-selected {{
      z-index: 2;
      outline: 3px solid #13151b;
      outline-offset: -4px;
      box-shadow: 0 10px 22px rgba(12, 41, 126, 0.18), inset 0 0 0 3px rgba(255,255,255,0.9);
    }}
    .hz-segment.hz-selected .hz-letter {{
      width: 32px;
      height: 32px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      border: 3px solid #fff;
      background: rgba(15, 23, 42, 0.18);
    }}
    .hz-segment.hz-selected::before {{
      content: "";
      position: absolute;
      top: -12px;
      left: 50%;
      transform: translateX(-50%);
      width: 0;
      height: 0;
      border-left: 8px solid transparent;
      border-right: 8px solid transparent;
      border-top: 0;
      border-bottom: 10px solid #111827;
    }}
    .hz-label-row {{
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 0;
      margin-top: 8px;
      font-size: 12px;
      color: var(--hz-muted);
      text-align: center;
      font-weight: 560;
    }}
    .hz-description {{
      margin-top: 16px;
      font-size: 14px;
      line-height: 1.55;
      color: rgba(19, 21, 27, 0.75);
    }}
    .hz-subtitle {{
      margin-top: 14px;
      margin-bottom: 6px;
      font-size: 13px;
      font-weight: 720;
      color: #13151b;
      letter-spacing: -0.025em;
    }}
    .hz-risk-signals ul {{
      margin: 0;
      padding-left: 0;
      color: rgba(19, 21, 27, 0.74);
      font-size: 13px;
      line-height: 1.45;
      list-style: none;
      display: grid;
      gap: 6px;
    }}
    .hz-risk-signals li {{
      border: 1px solid var(--hz-soft-border);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.62);
      padding: 8px 10px;
    }}
    .hz-food-flags {{
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid var(--hz-soft-border);
    }}
    .hz-food-flags .hz-subtitle {{
      font-size: 18px;
      font-weight: 760;
      letter-spacing: -0.045em;
      margin-bottom: 12px;
    }}
    .hz-food-flag-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .hz-food-flag {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      background: #ffeef2;
      color: rgba(19, 21, 27, 0.78);
      border: 1px solid var(--hz-soft-border);
      padding: 6px 10px;
      font-size: 14px;
      font-weight: 500;
    }}
    .hz-footnote {{
      margin-top: 7px;
      font-size: 12px;
      color: var(--hz-muted);
    }}
    @media (max-width: 520px) {{
      .hazardly-score-card {{ padding: 15px 12px; border-radius: 24px; }}
      .hz-header {{ align-items: flex-start; flex-direction: column; gap: 6px; }}
      .hz-segment {{ min-height: 40px; font-size: 14px; }}
      .hz-segment.hz-selected .hz-letter {{ width: 28px; height: 28px; }}
      .hz-label-row {{ font-size: 10px; }}
    }}
  </style>
  <div class="hz-header">
    <div class="hz-title">{html.escape(self.title)}</div>
    <div class="hz-grade-pill">Grade {score} - {html.escape(GRADE_META[score]["label"])}</div>
  </div>
  <div class="hz-bar" role="img" aria-label="Hazardly Score {score}">
    {segments}
  </div>
  <div class="hz-label-row">
    <span>Low</span><span>Mild</span><span>Moderate</span><span>High</span><span>Very high</span>
  </div>
  <div class="hz-description">{html.escape(description)}</div>
  {risk_block}
  {food_block}
</section>
""".strip()


def normalize_score(score: str | None) -> HazardlyGrade:
    grade = (score or "A").strip().upper()
    return grade if grade in GRADE_META else "A"  # type: ignore[return-value]


def render_hazardly_score_html(api_result: dict[str, Any] | None, input_text: str = "") -> str:
    if not api_result:
        return ""
    return hazardly_score_from_api_result(api_result, input_text=input_text).to_html()


def hazardly_score_from_api_result(api_result: dict[str, Any], input_text: str = "") -> HazardlyScoreBar:
    structured = api_result.get("structured_risk_output") or (
        api_result if "product_summary" in api_result else {}
    )
    structured = _best_structured_risk_output(api_result, structured, input_text)
    summary = structured.get("product_summary") or {}
    risks = [risk for risk in structured.get("identified_risks", []) if isinstance(risk, dict)]
    category_text = " ".join(
        str(part or "")
        for part in [
            summary.get("product_category"),
            (api_result.get("inferred_category") or {}).get("product_use_category"),
            (api_result.get("url_context") or {}).get("category"),
            api_result.get("input_mode"),
        ]
    )
    combined_input_text = " ".join([_api_input_text(api_result), input_text or ""]).strip()
    is_food = _is_food_context(category_text, combined_input_text)
    nutrition_flags = _nutrition_flags(risks, combined_input_text, is_food)
    hazard_risks = [risk for risk in risks if not _is_nutrition_only_risk(risk)]
    score = _score_from_hazard_risks(hazard_risks)
    risk_signals = _risk_signals(hazard_risks)
    return HazardlyScoreBar(
        score=score,
        description=GRADE_META[score]["description"],
        riskSignals=risk_signals,
        isFood=is_food,
        nutritionFlags=nutrition_flags,
    )


def _api_input_text(api_result: dict[str, Any]) -> str:
    structured = api_result.get("structured_risk_output") or {}
    summary = structured.get("product_summary") or {}
    return " ".join(
        str(part or "")
        for part in [
            (api_result.get("url_context") or {}).get("ingredients_text"),
            api_result.get("ingredients_text"),
            api_result.get("nutrition_text"),
            api_result.get("raw_ocr_text"),
            summary.get("product_name"),
        ]
    )


def _best_structured_risk_output(api_result: dict[str, Any], structured: dict[str, Any], input_text: str = "") -> dict[str, Any]:
    try:
        from product_risk_formatter import risk_output_from_api_result

        local_structured = risk_output_from_api_result(
            api_result,
            product_name=(structured.get("product_summary") or {}).get("product_name"),
            ingredients_text=" ".join(
                part
                for part in [
                    (api_result.get("url_context") or {}).get("ingredients_text", ""),
                    api_result.get("ingredients_text", ""),
                    input_text,
                ]
                if str(part or "").strip()
            ),
        )
    except Exception:
        return structured

    existing_risks = structured.get("identified_risks") or []
    local_risks = local_structured.get("identified_risks") or []
    if len(local_risks) > len(existing_risks):
        return local_structured
    if not structured and local_structured:
        return local_structured
    return structured


def nutrition_score_from_text(text: str) -> HazardlyScoreBar | None:
    facts = _parse_nutrition_facts(text)
    if not facts:
        # Check if we at least saw the words "nutrition facts"
        if re.search(r"(?i)nutrition facts", text):
            return HazardlyScoreBar(
                score="A",
                title="Nutrition Score",
                description="Nutrition facts missing — nutrition score unavailable.",
                isFood=False,
            )
        return None

    signals: list[str] = []
    penalties = 0

    added_sugar_dv = facts.get("added_sugars_dv")
    added_sugars_g = facts.get("added_sugars_g")
    total_sugars_g = facts.get("total_sugars_g")
    saturated_fat_dv = facts.get("saturated_fat_dv")
    saturated_fat_g = facts.get("saturated_fat_g")
    sodium_dv = facts.get("sodium_dv")
    sodium_mg = facts.get("sodium_mg")
    serving_size_g = facts.get("serving_size_g")
    calories = facts.get("calories")

    # 1. Added Sugar (%DV)
    if added_sugar_dv is not None:
        if added_sugar_dv >= 20:
            penalties += 2
            signals.append(f"High added sugar: {added_sugars_g:g}g added sugar, {added_sugar_dv:g}% DV")
        elif added_sugar_dv >= 5:
            signals.append(f"Moderate added sugar: {added_sugars_g:g}g added sugar, {added_sugar_dv:g}% DV")
        else:
            signals.append(f"Low added sugar: {added_sugars_g:g}g added sugar, {added_sugar_dv:g}% DV")
    elif added_sugars_g is not None and added_sugars_g >= 10:
        penalties += 1
        signals.append(f"Added sugar: {added_sugars_g:g}g (No %DV provided)")

    # 2. Total Sugar Density (Weight Ratio)
    if total_sugars_g is not None and serving_size_g:
        ratio = total_sugars_g / serving_size_g
        if ratio >= 0.30:
            penalties += 2 if ratio >= 0.50 else 1
            signals.append(f"High total sugar density: {total_sugars_g:g}g sugar per {serving_size_g:g}g serving")

    # 3. Saturated Fat (%DV)
    if saturated_fat_dv is not None:
        if saturated_fat_dv >= 20:
            penalties += 2
            signals.append(f"High saturated fat: {saturated_fat_g:g}g saturated fat, {saturated_fat_dv:g}% DV")
        elif saturated_fat_dv >= 5:
            signals.append(f"Moderate saturated fat: {saturated_fat_g:g}g saturated fat, {saturated_fat_dv:g}% DV")
        else:
            signals.append(f"Low saturated fat: {saturated_fat_g:g}g saturated fat, {saturated_fat_dv:g}% DV")

    # 4. Sodium (%DV)
    if sodium_dv is not None:
        if sodium_dv >= 20:
            penalties += 2 if sodium_dv >= 40 else 1
            signals.append(f"High sodium: {sodium_mg:g}mg sodium, {sodium_dv:g}% DV")
        elif sodium_dv >= 5:
            signals.append(f"Moderate sodium: {sodium_mg:g}mg sodium, {sodium_dv:g}% DV")
        else:
            signals.append(f"Low sodium: {sodium_mg:g}mg sodium, {sodium_dv:g}% DV")

    # Map penalties to grades: A=0, B=1, C=2, D=3, E=4+
    grade_idx = min(penalties, 4)

    # Constraints
    # No A or B if Added Sugar >= 20% DV OR Saturated Fat >= 20% DV
    if (added_sugar_dv is not None and added_sugar_dv >= 20) or (saturated_fat_dv is not None and saturated_fat_dv >= 20):
        grade_idx = max(grade_idx, 3) # Force D or E (Idx 3 or 4)

    # No A, B, or C if Added Sugar >= 30% DV AND Saturated Fat >= 20% DV
    if (added_sugar_dv is not None and added_sugar_dv >= 30) and (saturated_fat_dv is not None and saturated_fat_dv >= 20):
        grade_idx = max(grade_idx, 3) # Force D or E

    grades: list[HazardlyGrade] = ["A", "B", "C", "D", "E"]
    score = grades[grade_idx]

    explanation = ""
    if grade_idx >= 3:
        explanation = "This serving is high in added sugar and/or saturated fat."
        if sodium_dv is not None and sodium_dv < 5:
            explanation += " Sodium is low, but it does not offset the sugar and saturated-fat flags."
    elif grade_idx == 0:
        explanation = "Nutrition Score: label values do not show major sugar, sodium, or saturated-fat flags for this serving."
    else:
        explanation = "Nutrition Score reflects moderate levels of sugar, fat, or sodium."

    return HazardlyScoreBar(
        score=score,
        title="Nutrition Score",
        description=explanation,
        riskSignals=signals,
        isFood=False,
    )


def _parse_nutrition_facts(text: str) -> dict[str, float]:
    normalized = _norm(text)
    if not normalized or not re.search(r"nutrition facts|calories|total fat|sodium|total sugars|added sugars", normalized):
        return {}

    facts: dict[str, float] = {}
    
    # Try to find serving size in grams: e.g. "2 tbsp (37g)" or "Serving size 37g"
    serving_match = re.search(r"serving\s+size[:\s]*.*?\(([\d.]+)g\)", normalized) or re.search(r"serving\s+size[:\s]*([\d.]+)g", normalized)
    if serving_match:
        try:
            facts["serving_size_g"] = float(serving_match.group(1))
        except ValueError:
            pass

    calories = _first_number(r"\bcalories[:\s]*(?:\s+per\s+serving)?[:\s]*(\d+(?:\.\d+)?)", normalized)
    if calories is not None:
        facts["calories"] = calories
    total_sugars = _first_number(r"\btotal\s+sugars?[:\s]*(?:<\s*)?(\d+(?:\.\d+)?)\s*g", normalized)
    if total_sugars is not None:
        facts["total_sugars_g"] = total_sugars
    added_sugars = _first_number(r"\b(?:includes?\s*)?added\s+sugars?[:\s]*(?:<\s*)?(\d+(?:\.\d+)?)\s*g", normalized)
    if added_sugars is not None:
        facts["added_sugars_g"] = added_sugars
    added_sugars_dv = _first_number(r"\b(?:includes?\s*)?added\s+sugars?[:\s]*(?:<\s*)?\d+(?:\.\d+)?\s*g\s*(\d+(?:\.\d+)?)\s*%", normalized)
    if added_sugars_dv is not None:
        facts["added_sugars_dv"] = added_sugars_dv
    saturated_fat = _first_number(r"\bsaturated\s+fat[:\s]*(?:<\s*)?(\d+(?:\.\d+)?)\s*g", normalized)
    if saturated_fat is not None:
        facts["saturated_fat_g"] = saturated_fat
    saturated_fat_dv = _first_number(r"\bsaturated\s+fat[:\s]*(?:<\s*)?\d+(?:\.\d+)?\s*g\s*(\d+(?:\.\d+)?)\s*%", normalized)
    if saturated_fat_dv is not None:
        facts["saturated_fat_dv"] = saturated_fat_dv
    sodium = _first_number(r"\bsodium[:\s]*(?:<\s*)?(\d+(?:\.\d+)?)\s*mg", normalized)
    if sodium is not None:
        facts["sodium_mg"] = sodium
    sodium_dv = _first_number(r"\bsodium[:\s]*(?:<\s*)?\d+(?:\.\d+)?\s*mg\s*(\d+(?:\.\d+)?)\s*%", normalized)
    if sodium_dv is not None:
        facts["sodium_dv"] = sodium_dv
    fiber = _first_number(r"\bdietary\s+fiber[:\s]*(?:<\s*)?(\d+(?:\.\d+)?)\s*g", normalized)
    if fiber is not None:
        facts["fiber_g"] = fiber
    return facts


def _first_number(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.I)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _segment_html(grade: str, *, selected: bool) -> str:
    meta = GRADE_META[normalize_score(grade)]
    selected_class = " hz-selected" if selected else ""
    return (
        f"<div class='hz-segment{selected_class}' style='background:{meta['color']}' "
        f"aria-label='Grade {grade}: {html.escape(meta['label'])}'>"
        f"<span class='hz-letter'>{grade}</span></div>"
    )


def _score_from_hazard_risks(risks: list[dict[str, Any]]) -> HazardlyGrade:
    if not risks:
        return "A"
    max_rank = max(_risk_rank(risk) for risk in risks)
    strong_count = sum(1 for risk in risks if _risk_rank(risk) >= 3)
    if max_rank >= 4 or strong_count >= 3:
        return "E"
    if max_rank == 3:
        return "D"
    if max_rank == 2:
        return "C"
    return "B"


def _risk_rank(risk: dict[str, Any]) -> int:
    caution = _norm(risk.get("caution_level") or risk.get("user_recommendation"))
    confidence = _norm(risk.get("confidence_level") or risk.get("confidence"))
    basis = _norm(risk.get("detection_basis") or risk.get("identification_method"))
    source_text = _norm(" ".join(str(source) for source in risk.get("risk_sources", []) or []))

    rank = 1
    if "use with caution" in caution or "avoid if allergic" in caution:
        rank = 2
    if "limit frequent exposure" in caution or "avoid for sensitive groups" in caution:
        rank = 3
    if any(token in source_text for token in ["recall", "banned", "prohibited", "do not use"]):
        rank = 4
    if "listed ingredient" in basis and any(token in confidence for token in ["explicit", "high"]):
        rank = max(rank, 2)
    if "cancer" in source_text and "listed ingredient" in basis and any(token in confidence for token in ["explicit", "high"]):
        rank = max(rank, 3)
    return rank


def _risk_signals(risks: list[dict[str, Any]]) -> list[str]:
    ranked = sorted(risks, key=_risk_rank, reverse=True)
    signals: list[str] = []
    for risk in ranked[:5]:
        name = str(risk.get("chemical_name") or "Risk signal").strip()
        basis = str(risk.get("detection_basis") or risk.get("identification_method") or "screening signal").strip()
        evidence = str(risk.get("evidence_from_product") or "").strip()
        if evidence:
            signals.append(f"{name} - {basis}; clue: {evidence}")
        else:
            signals.append(f"{name} - {basis}")
    return signals


def _nutrition_flags(risks: list[dict[str, Any]], input_text: str, is_food: bool) -> list[str]:
    if not is_food:
        return []
    text = _norm(input_text)
    flags: list[str] = []
    if any(_is_added_sugar_risk(risk) for risk in risks) or re.search(r"\b(high[-\s]?fructose\s+corn\s+syrup|corn\s+syrup|added\s+sugars?|includes?\s+added\s+sugars?|cane\s+sugar|sugar)\b", text):
        flags.append("High added sugar")
    if re.search(r"\b(sodium|salt|sea\s+salt|monosodium\s+glutamate|msg)\b", text):
        flags.append("High sodium")
    if re.search(r"\b(palm\s+oil|palm\s+kernel|vegetable\s+fats?|coconut\s+oil|butter|cream|hydrogenated\s+oil|shortening|saturated\s+fat)\b", text):
        flags.append("High saturated fat")
    if re.search(r"\b(artificial\s+color|fd&c|red\s+\d+|yellow\s+\d+|blue\s+\d+|preservative|corn\s+syrup|hydrogenated|modified\s+starch)\b", text):
        flags.append("Ultra-processed")
    if re.search(r"\b(wheat|soy|egg|milk|peanut|tree\s+nut|almond|cashew|walnut|sesame|shellfish|fish)\b", text):
        flags.append("Common allergens")
    return list(dict.fromkeys(flags))


def _is_nutrition_only_risk(risk: dict[str, Any]) -> bool:
    text = _norm(
        " ".join(
            str(risk.get(key) or "")
            for key in ["chemical_name", "consumer_explanation", "dose_context", "evidence_from_product"]
        )
    )
    source_text = _norm(" ".join(str(source) for source in risk.get("risk_sources", []) or []))
    return _is_added_sugar_risk(risk) or "metabolic concern" in source_text or "nutrition context" in text


def _is_added_sugar_risk(risk: dict[str, Any]) -> bool:
    text = _norm(" ".join(str(risk.get(key) or "") for key in ["chemical_name", "evidence_from_product"]))
    return "added sugars" in text or "corn syrup" in text or "high-fructose" in text


def _is_food_context(category_text: str, input_text: str) -> bool:
    text = _norm(f"{category_text} {input_text}")
    return any(
        token in text
        for token in [
            "food",
            "grocery",
            "snack",
            "beverage",
            "drink",
            "tea",
            "coffee",
            "meat",
            "cookie",
            "chips",
            "candy",
            "ingredients",
        ]
    )


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()
