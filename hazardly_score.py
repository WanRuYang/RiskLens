from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any, Literal


HazardlyGrade = Literal["A", "B", "C", "D", "E"]
FlagType = Literal[
    "chemical_process",
    "regulatory",
    "contaminant",
    "material_safety",
    "confirmed_hazardous_ingredient",
    "nutrition",
    "allergen",
    "ingredient_note",
    "serving_size_note",
    "general_product_info",
]
FlagSeverity = Literal["info", "low", "moderate", "high", "critical"]
FlagConfidence = Literal["weak", "possible", "likely", "confirmed", "measured"]
FlagScoreImpact = Literal["none", "low", "medium", "high"]
FlagEvidenceSource = Literal[
    "lab_result",
    "product_warning",
    "recall_or_enforcement",
    "food_regulatory_restriction",
    "label_ingredient",
    "process_inference",
    "packaging_inference",
    "category_prior",
    "regulatory_list",
    "nutrition_label",
    "allergen_label",
    "general_info",
]
FlagRouteRelevance = Literal["none", "uncertain", "food_or_oral"]
FlagExposureLikelihood = Literal[
    "theoretical",
    "inferred",
    "direct_unknown_dose",
    "likely_meaningful",
    "measured",
]
FlagPopulationFactor = Literal["general_population", "infant_child_pregnancy_targeted"]

SCORE_AFFECTING_FLAG_TYPES = {
    "chemical_process",
    "regulatory",
    "contaminant",
    "material_safety",
    "confirmed_hazardous_ingredient",
}
NON_SCORING_FLAG_TYPES = {
    "nutrition",
    "allergen",
    "ingredient_note",
    "serving_size_note",
    "general_product_info",
}


GRADE_META: dict[HazardlyGrade, dict[str, str]] = {
    "A": {
        "label": "Low chemical/process concern",
        "color": "#2e9e5d",
        "description": (
            "Low chemical/process concern: No meaningful chemical, process, contaminant, "
            "material-safety, or regulatory concern survived relevance filters."
        ),
    },
    "B": {
        "label": "Minor chemical/process concern",
        "color": "#2f9c95",
        "description": (
            "Minor chemical/process concern: One weak or possible concern was found; it is mostly informational."
        ),
    },
    "C": {
        "label": "Moderate chemical/process concern",
        "color": "#facc15",
        "description": (
            "Moderate chemical/process concern: One meaningful but not decisive concern, or several smaller "
            "process/material concerns, survived relevance filters."
        ),
    },
    "D": {
        "label": "High chemical/process concern",
        "color": "#f97316",
        "description": (
            "High chemical/process concern: Strong food-relevant evidence, a confirmed high-concern ingredient, "
            "or multiple moderate/high chemical signals were identified."
        ),
    },
    "E": {
        "label": "Very high chemical/process concern",
        "color": "#ef4444",
        "description": (
            "Very high chemical/process concern: Measured exceedance, direct regulatory warning, "
            "infant-targeted high-priority concern, or multiple serious signals were identified."
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
class HazardlyFlag:
    label: str
    type: FlagType
    severity: FlagSeverity
    confidence: FlagConfidence
    evidenceSource: FlagEvidenceSource
    routeRelevance: FlagRouteRelevance
    exposureLikelihood: FlagExposureLikelihood
    populationFactor: FlagPopulationFactor
    scoreImpact: FlagScoreImpact
    riskPoints: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "type": self.type,
            "severity": self.severity,
            "confidence": self.confidence,
            "evidence_source": self.evidenceSource,
            "route_relevance": self.routeRelevance,
            "exposure_likelihood": self.exposureLikelihood,
            "population_factor": self.populationFactor,
            "score_impact": self.scoreImpact,
            "risk_points": self.riskPoints,
            "reason": self.reason,
        }


@dataclass
class HazardlyScoreBar:
    score: HazardlyGrade
    title: str = "Hazardly Score"
    description: str = ""
    riskSignals: list[str] = field(default_factory=list)
    isFood: bool = False
    nutritionFlags: list[str] = field(default_factory=list)
    flags: list[HazardlyFlag] = field(default_factory=list)
    totalRiskPoints: float = 0.0

    def to_html(self, *, include_flags: bool = True) -> str:
        score = normalize_score(self.score)
        description = self.description or GRADE_META[score]["description"]
        
        hazard_flags = [flag for flag in self.flags if flag.type in SCORE_AFFECTING_FLAG_TYPES]
        note_flags = [flag for flag in self.flags if flag.type in NON_SCORING_FLAG_TYPES]
        
        risk_items = "".join(
            f"<li>{html.escape(flag.label)}</li>"
            for flag in hazard_flags[:5]
            if flag.label.strip()
        )
        risk_block = (
            f"<div class='hz-risk-signals'><div class='hz-subtitle'>Key risk signals</div><ul>{risk_items}</ul></div>"
            if include_flags and risk_items
            else ""
        )
        
        flag_chips = []
        for flag in note_flags:
            cls = _css_class_for_flag_type(flag.type)
            flag_chips.append(f"<span class='hz-chip {cls}'>{html.escape(flag.label)}</span>")
        
        flags_html = "".join(flag_chips)
        food_block = (
            "<div class='hz-food-flags'>"
            "<div class='hz-subtitle'>Product notes</div>"
            f"<div class='hz-unified-flag-row'>{flags_html}</div>"
            "<div class='hz-footnote'>These informational notes do not affect the A-E Hazardly Score.</div>"
            "</div>"
            if include_flags and self.isFood and flags_html
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
      --hz-border: rgba(148, 163, 184, 0.2);
      --hz-soft-border: rgba(59, 130, 246, 0.1);
      --hz-text: #f8fafc;
      --hz-muted: #94a3b8;
      --hz-card: #1e293b;
      
      background: var(--hz-card);
      border: 1px solid var(--hz-border);
      border-radius: 32px;
      padding: 24px;
      font-family: "ReferoBase", -apple-system, sans-serif;
      color: var(--hz-text);
      box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }}
    .hz-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }}
    .hz-title {{
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.05em;
      color: #3b82f6;
    }}
    .hz-grade-pill {{
      border-radius: 999px;
      background: #3b82f6;
      color: #ffffff;
      font-size: 14px;
      font-weight: 700;
      padding: 6px 16px;
      box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.3);
    }}
    .hz-bar {{
      display: flex;
      gap: 6px;
      margin-bottom: 12px;
    }}
    .hz-segment {{
      flex: 1;
      height: 52px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      opacity: 0.2;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    .hz-segment.hz-selected {{
      opacity: 1;
      transform: scaleY(1.1);
      box-shadow: 0 0 20px rgba(255, 255, 255, 0.1);
    }}
    .hz-letter {{
      font-size: 20px;
      font-weight: 900;
      color: #fff;
    }}
    .hz-segment.hz-selected .hz-letter {{
      text-shadow: 0 0 8px rgba(255, 255, 255, 0.5);
    }}
    .hz-label-row {{
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      font-weight: 700;
      color: var(--hz-muted);
      padding: 0 4px;
      margin-bottom: 24px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }}
    .hz-description {{
      font-size: 16px;
      line-height: 1.6;
      color: #e2e8f0;
      margin-bottom: 20px;
      font-weight: 400;
    }}
    .hz-risk-signals, .hz-food-flags {{
      margin-top: 20px;
      padding-top: 16px;
      border-top: 1px solid var(--hz-line);
    }}
    .hz-subtitle {{
      font-size: 16px;
      font-weight: 800;
      margin-bottom: 12px;
      color: #2563eb;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .hz-risk-signals ul {{
      margin: 0;
      padding-left: 20px;
      font-size: 15px;
      color: #cbd5e1;
    }}
    .hz-risk-signals li {{
      margin-bottom: 8px;
    }}
    .hz-unified-flag-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .hz-chip {{
      display: inline-flex;
      align-items: center;
      border-radius: 8px;
      padding: 8px 14px;
      font-size: 14px;
      font-weight: 700;
      border: 1px solid transparent;
      text-transform: uppercase;
      letter-spacing: 0.02em;
    }}
    /* Flag Type Styles - Enterprise Dark */
    .hz-type-chemical {{ background: rgba(250, 204, 21, 0.1); color: #facc15; border-color: rgba(250, 204, 21, 0.4); }}
    .hz-type-regulatory {{ background: rgba(249, 115, 22, 0.1); color: #fb923c; border-color: rgba(249, 115, 22, 0.4); }}
    .hz-type-nutrition {{ background: rgba(59, 130, 246, 0.1); color: #60a5fa; border-color: rgba(59, 130, 246, 0.4); }}
    .hz-type-allergen {{ background: rgba(168, 85, 247, 0.1); color: #c084fc; border-color: rgba(168, 85, 247, 0.4); }}
    .hz-type-ingredient {{ background: rgba(148, 163, 184, 0.1); color: #94a3b8; border-color: rgba(148, 163, 184, 0.4); }}

    .hz-footnote {{
      margin-top: 16px;
      font-size: 13px;
      color: var(--hz-muted);
      line-height: 1.5;
      font-style: italic;
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
    return hazardly_score_from_api_result(api_result, input_text=input_text).to_html(include_flags=False)


def render_hazardly_flags_html(api_result: dict[str, Any] | None, input_text: str = "") -> str:
    if not api_result:
        return ""
    score = hazardly_score_from_api_result(api_result, input_text=input_text)
    
    # Combined scoring and non-scoring flags
    hazard_flags = [flag for flag in score.flags if flag.type in SCORE_AFFECTING_FLAG_TYPES]
    note_flags = [flag for flag in score.flags if flag.type in NON_SCORING_FLAG_TYPES]
    
    flag_chips = []
    for flag in hazard_flags[:5]:
        cls = _css_class_for_flag_type(flag.type)
        flag_chips.append(f"<span class='hz-chip {cls}'>{html.escape(flag.label)}</span>")
    
    for flag in note_flags:
        if flag.label in NUTRITION_FLAG_OPTIONS:
            cls = _css_class_for_flag_type(flag.type)
            flag_chips.append(f"<span class='hz-chip {cls}'>{html.escape(flag.label)}</span>")

    if not flag_chips:
        return """
<section class="hazardly-flags-card">
  <div class="hz-flags-title">Hazardly Flags</div>
  <div class="hz-empty-flags">No additional hazard or food flags were identified from the available input.</div>
</section>
""".strip()
    
    flags_row = f"<div class='hz-unified-flag-row'>{''.join(flag_chips)}</div>"
    
    # Update footnote to reflect new chip colors
    footnote = (
        "<div class='hz-footnote'>Amber chips: processing signals. Orange: regulatory/material concern. Blue: nutrition. Lavender: allergen. Gray: ingredient notes. These flags do not affect the A-E Hazardly Score.</div>"
        if score.isFood
        else "<div class='hz-footnote'>Amber/Orange chips reflect processing or material concern signals.</div>"
    )
    
    return f"""
<section class="hazardly-flags-card">
  <div class="hz-flags-title">Hazardly Flags</div>
  {flags_row}
  {footnote}
</section>
""".strip()


def _css_class_for_flag_type(flag_type: FlagType) -> str:
    if flag_type == "chemical_process":
        return "hz-type-chemical"
    if flag_type in {"regulatory", "contaminant", "material_safety", "confirmed_hazardous_ingredient"}:
        return "hz-type-regulatory"
    if flag_type == "nutrition":
        return "hz-type-nutrition"
    if flag_type == "allergen":
        return "hz-type-allergen"
    return "hz-type-ingredient"


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
    flags = _flags_from_risks(risks, is_food=is_food) + _nutrition_note_flags(nutrition_flags)
    scoring_flags = [flag for flag in flags if _flag_affects_score(flag)]
    score = _score_from_flags(scoring_flags)
    risk_signals = _risk_signals_from_flags(scoring_flags)
    return HazardlyScoreBar(
        score=score,
        description=GRADE_META[score]["description"],
        riskSignals=risk_signals,
        isFood=is_food,
        nutritionFlags=nutrition_flags,
        flags=flags,
        totalRiskPoints=round(sum(flag.riskPoints for flag in scoring_flags), 4),
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


def _score_from_flags(flags: list[HazardlyFlag]) -> HazardlyGrade:
    total_points = sum(flag.riskPoints for flag in flags if _flag_affects_score(flag))
    if total_points <= 0.75:
        return "A"
    if total_points <= 1.75:
        return "B"
    if total_points <= 3.0:
        return "C"
    if total_points <= 4.5:
        return "D"
    return "E"


def _flag_impact_rank(flag: HazardlyFlag) -> int:
    return {"none": 0, "low": 1, "medium": 2, "high": 3}.get(flag.scoreImpact, 0)


def _flag_affects_score(flag: HazardlyFlag) -> bool:
    return flag.type in SCORE_AFFECTING_FLAG_TYPES and flag.scoreImpact != "none"


def _risk_signals_from_flags(flags: list[HazardlyFlag]) -> list[str]:
    ranked = sorted(flags, key=lambda flag: (flag.riskPoints, _flag_impact_rank(flag)), reverse=True)
    return [flag.label for flag in ranked[:5] if flag.label.strip()]


def _nutrition_flags(risks: list[dict[str, Any]], input_text: str, is_food: bool) -> list[str]:
    if not is_food:
        return []
    text = _norm(input_text)
    facts = _parse_nutrition_facts(input_text)
    flags: list[str] = []
    if any(_is_added_sugar_risk(risk) for risk in risks) or re.search(r"\b(high[-\s]?fructose\s+corn\s+syrup|corn\s+syrup|added\s+sugars?|includes?\s+added\s+sugars?|cane\s+sugar|sugar)\b", text):
        flags.append("High added sugar")
    sodium_dv = facts.get("sodium_dv")
    sodium_mg = facts.get("sodium_mg")
    if (sodium_dv is not None and sodium_dv >= 20) or (sodium_mg is not None and sodium_mg >= 460):
        flags.append("High sodium")
    if re.search(r"\b(palm\s+oil|palm\s+kernel|vegetable\s+fats?|coconut\s+oil|butter|cream|hydrogenated\s+oil|shortening|saturated\s+fat)\b", text):
        flags.append("High saturated fat")
    if re.search(r"\b(artificial\s+color|fd&c|red\s+\d+|yellow\s+\d+|blue\s+\d+|preservative|corn\s+syrup|hydrogenated|modified\s+starch)\b", text):
        flags.append("Ultra-processed")
    return list(dict.fromkeys(flags))


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


def _flags_from_risks(risks: list[dict[str, Any]], *, is_food: bool) -> list[HazardlyFlag]:
    flags: list[HazardlyFlag] = []
    for risk in risks:
        flag_type = _flag_type(risk)
        severity = _flag_severity(risk)
        confidence = _flag_confidence(risk)
        evidence_source = _flag_evidence_source(risk, flag_type)
        route_relevance = _flag_route_relevance(risk, flag_type, is_food=is_food)
        exposure_likelihood = _flag_exposure_likelihood(risk, evidence_source)
        population_factor = _flag_population_factor(risk)
        risk_points = _weighted_risk_points(
            severity=severity,
            confidence=confidence,
            exposure_likelihood=exposure_likelihood,
            route_relevance=route_relevance,
            population_factor=population_factor,
        )
        score_impact = _score_impact_from_points(risk_points, flag_type)
        label = _flag_label(risk)
        reason = str(risk.get("consumer_explanation") or risk.get("evidence_from_product") or "").strip()
        flags.append(
            HazardlyFlag(
                label=label,
                type=flag_type,
                severity=severity,
                confidence=confidence,
                evidenceSource=evidence_source,
                routeRelevance=route_relevance,
                exposureLikelihood=exposure_likelihood,
                populationFactor=population_factor,
                scoreImpact=score_impact,
                riskPoints=risk_points,
                reason=reason or "Screening signal from available product information.",
            )
        )
    return flags


def _nutrition_note_flags(nutrition_flags: list[str]) -> list[HazardlyFlag]:
    return [
        HazardlyFlag(
            label=flag,
            type="nutrition",
            severity="low",
            confidence="possible",
            evidenceSource="nutrition_label",
            routeRelevance="none",
            exposureLikelihood="direct_unknown_dose",
            populationFactor="general_population",
            scoreImpact="none",
            riskPoints=0.0,
            reason="Nutrition note from the available ingredient or Nutrition Facts text.",
        )
        for flag in nutrition_flags
    ]


def _flag_label(risk: dict[str, Any]) -> str:
    name = str(risk.get("chemical_name") or "Risk signal").strip()
    basis = _norm(risk.get("detection_basis") or risk.get("identification_method"))
    if name.lower() == "acrylamide" and "process" in basis:
        return "Possible acrylamide formation"
    return name


def _flag_type(risk: dict[str, Any]) -> FlagType:
    explicit = _norm(risk.get("signal_type"))
    valid = SCORE_AFFECTING_FLAG_TYPES | NON_SCORING_FLAG_TYPES
    if explicit in valid:
        return explicit  # type: ignore[return-value]
    name = _norm(risk.get("chemical_name"))
    basis = _norm(risk.get("detection_basis") or risk.get("identification_method"))
    if _is_added_sugar_risk(risk):
        return "nutrition"
    if "allerg" in _norm(" ".join(str(source) for source in risk.get("risk_sources", []) or [])):
        return "allergen"
    if "glycidyl" in name or "3-mcpd" in name:
        return "contaminant"
    if "packaging" in basis:
        return "material_safety"
    if "process" in basis:
        return "chemical_process"
    if "listed ingredient" in basis:
        return "confirmed_hazardous_ingredient"
    return "ingredient_note"


def _flag_severity(risk: dict[str, Any]) -> FlagSeverity:
    explicit = _norm(risk.get("severity"))
    if explicit in {"info", "low", "moderate", "high", "critical"}:
        return explicit  # type: ignore[return-value]
    impact = _flag_score_impact(risk, _flag_type(risk))
    return {"none": "info", "low": "low", "medium": "moderate", "high": "high"}[impact]  # type: ignore[return-value]


def _flag_confidence(risk: dict[str, Any]) -> FlagConfidence:
    raw = _norm(risk.get("confidence_level") or risk.get("confidence"))
    if raw == "measured":
        return "measured"
    if raw in {"explicit", "confirmed", "high"}:
        return "confirmed"
    if raw in {"likely", "medium"}:
        return "likely"
    if raw in {"possible", "low"}:
        return "possible"
    return "weak"


def _flag_score_impact(risk: dict[str, Any], flag_type: FlagType) -> FlagScoreImpact:
    if flag_type in NON_SCORING_FLAG_TYPES:
        return "none"
    explicit = _norm(risk.get("score_impact"))
    if explicit in {"none", "low", "medium", "high"}:
        return explicit  # type: ignore[return-value]
    name = _norm(risk.get("chemical_name"))
    evidence = _norm(risk.get("evidence_from_product"))
    confidence = _flag_confidence(risk)
    if "acrylamide" in name:
        return "low"
    if "glycidyl" in name or "3-mcpd" in name:
        return "medium" if any(token in evidence for token in ["palm oil", "palm kernel", "refined palm"]) else "low"
    if flag_type == "material_safety":
        return "high" if confidence in {"confirmed", "likely"} else "medium"
    if flag_type == "confirmed_hazardous_ingredient":
        return "high" if confidence == "confirmed" else "medium"
    return "low"


def _flag_evidence_source(risk: dict[str, Any], flag_type: FlagType) -> FlagEvidenceSource:
    explicit = _norm(risk.get("evidence_source"))
    valid = {
        "lab_result",
        "product_warning",
        "recall_or_enforcement",
        "food_regulatory_restriction",
        "label_ingredient",
        "process_inference",
        "packaging_inference",
        "category_prior",
        "regulatory_list",
        "nutrition_label",
        "allergen_label",
        "general_info",
    }
    if explicit in valid:
        return explicit  # type: ignore[return-value]
    basis = _norm(risk.get("detection_basis") or risk.get("identification_method"))
    if flag_type == "nutrition":
        return "nutrition_label"
    if flag_type == "allergen":
        return "allergen_label"
    if flag_type == "contaminant" or flag_type == "chemical_process":
        return "process_inference"
    if flag_type == "material_safety" or "packaging" in basis:
        return "packaging_inference"
    if flag_type == "confirmed_hazardous_ingredient":
        return "label_ingredient"
    if "category" in basis:
        return "category_prior"
    return "regulatory_list"


def _flag_route_relevance(risk: dict[str, Any], flag_type: FlagType, *, is_food: bool) -> FlagRouteRelevance:
    text = _norm(
        " ".join(
            str(risk.get(key) or "")
            for key in ["chemical_name", "evidence_from_product", "consumer_explanation", "dose_context"]
        )
    )
    food_contact_material = flag_type == "material_safety" and any(
        token in text
        for token in ["food container", "food packaging", "food/drink can", "can-lining", "cookware", "frying pan", "non-stick"]
    )
    explicit = _norm(risk.get("route_relevance"))
    if explicit in {"none", "uncertain", "food_or_oral"}:
        if explicit == "uncertain" and food_contact_material:
            return "food_or_oral"
        if explicit == "food_or_oral" and not is_food and flag_type not in {"nutrition", "allergen"}:
            if food_contact_material:
                return "food_or_oral"
            return "uncertain"
        return explicit  # type: ignore[return-value]
    if flag_type in NON_SCORING_FLAG_TYPES:
        return "none"
    if flag_type in {"chemical_process", "contaminant"}:
        return "food_or_oral" if is_food else "uncertain"
    if flag_type == "confirmed_hazardous_ingredient":
        return "food_or_oral" if is_food else "uncertain"
    if food_contact_material:
        return "food_or_oral"
    return "uncertain"


def _flag_exposure_likelihood(risk: dict[str, Any], evidence_source: FlagEvidenceSource) -> FlagExposureLikelihood:
    explicit = _norm(risk.get("exposure_likelihood"))
    if explicit in {"theoretical", "inferred", "direct_unknown_dose", "likely_meaningful", "measured"}:
        return explicit  # type: ignore[return-value]
    return {
        "lab_result": "measured",
        "product_warning": "direct_unknown_dose",
        "recall_or_enforcement": "likely_meaningful",
        "food_regulatory_restriction": "direct_unknown_dose",
        "label_ingredient": "direct_unknown_dose",
        "process_inference": "inferred",
        "packaging_inference": "inferred",
        "category_prior": "theoretical",
        "regulatory_list": "theoretical",
        "nutrition_label": "direct_unknown_dose",
        "allergen_label": "direct_unknown_dose",
        "general_info": "theoretical",
    }[evidence_source]  # type: ignore[return-value]


def _flag_population_factor(risk: dict[str, Any]) -> FlagPopulationFactor:
    explicit = _norm(risk.get("population_factor"))
    if explicit in {"general_population", "infant_child_pregnancy_targeted"}:
        return explicit  # type: ignore[return-value]
    product_text = _norm(
        " ".join(
            str(risk.get(key) or "")
            for key in ["evidence_from_product", "consumer_explanation", "dose_context"]
        )
    )
    if any(token in product_text for token in ["infant", "baby", "children's", "child-targeted", "pregnancy"]):
        return "infant_child_pregnancy_targeted"
    return "general_population"


def _weighted_risk_points(
    *,
    severity: FlagSeverity,
    confidence: FlagConfidence,
    exposure_likelihood: FlagExposureLikelihood,
    route_relevance: FlagRouteRelevance,
    population_factor: FlagPopulationFactor,
) -> float:
    severity_value = {"info": 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}[severity]
    evidence_value = {"weak": 0.25, "possible": 0.50, "likely": 0.75, "confirmed": 1.0, "measured": 1.25}[confidence]
    exposure_value = {
        "theoretical": 0.25,
        "inferred": 0.50,
        "direct_unknown_dose": 0.75,
        "likely_meaningful": 1.0,
        "measured": 1.0,
    }[exposure_likelihood]
    route_value = {"none": 0.0, "uncertain": 0.5, "food_or_oral": 1.0}[route_relevance]
    population_value = {"general_population": 1.0, "infant_child_pregnancy_targeted": 1.25}[population_factor]
    return round(severity_value * evidence_value * exposure_value * route_value * population_value, 4)


def _score_impact_from_points(points: float, flag_type: FlagType) -> FlagScoreImpact:
    if flag_type in NON_SCORING_FLAG_TYPES or points <= 0:
        return "none"
    if points <= 0.75:
        return "low"
    if points <= 1.75:
        return "medium"
    return "high"


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()
