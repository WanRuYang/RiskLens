from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any, Literal


RiskLensGrade = Literal["A", "B", "C", "D", "E"]
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


GRADE_META: dict[RiskLensGrade, dict[str, str]] = {
    "A": {
        "label": "Low chemical/process concern",
        "color": "#2E9E5D",
        "description": (
            "Low chemical/process concern: No meaningful chemical, process, contaminant, "
            "material-safety, or regulatory concern survived relevance filters."
        ),
    },
    "B": {
        "label": "Minor chemical/process concern",
        "color": "#2F9C95",
        "description": (
            "Minor chemical/process concern: One low-confidence or low-impact chemical/process signal was detected. "
            "This is a screening signal, not confirmation that this product is unsafe."
        ),
    },
    "C": {
        "label": "Moderate chemical/process concern",
        "color": "#F4C542",
        "description": (
            "Moderate chemical/process concern: Multiple process-related signals were detected, such as possible "
            "high-temperature cooking byproducts or refined-oil processing contaminants. These are screening "
            "signals, not confirmation that this specific product is unsafe."
        ),
    },
    "D": {
        "label": "High chemical/process concern",
        "color": "#F28A2E",
        "description": (
            "High chemical/process concern: Strong food-relevant evidence, a confirmed high-concern ingredient, "
            "or multiple moderate/high chemical signals were identified."
        ),
    },
    "E": {
        "label": "Very high chemical/process concern",
        "color": "#D94747",
        "description": (
            "Very high chemical/process concern: Measured exceedance, direct regulatory warning, "
            "infant-targeted high-priority concern, or multiple serious signals were identified."
        ),
    },
}

SCOPE_NOTE = (
    "RiskLens Score reflects chemical, regulatory, contaminant, material-safety, and processing-related signals. "
    "Nutrition, allergen, and ingredient notes are shown separately as additional context."
)


NUTRITION_FLAG_OPTIONS = {
    "High added sugar",
    "High sugar",
    "High sodium",
    "High saturated fat",
    "Ultra-processed",
    "Common allergens",
}


@dataclass
class RiskLensFlag:
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
class RiskLensScoreBar:
    score: RiskLensGrade
    title: str = "RiskLens Score"
    description: str = ""
    riskSignals: list[str] = field(default_factory=list)
    isFood: bool = False
    nutritionFlags: list[str] = field(default_factory=list)
    flags: list[RiskLensFlag] = field(default_factory=list)
    totalRiskPoints: float = 0.0

    def to_html(self, *, include_flags: bool = True) -> str:
        score = normalize_score(self.score)
        description = self.description or GRADE_META[score]["description"]
        
        # Categorical separation logic
        chemical_flags = [f for f in self.flags if f.type in {"chemical_process", "regulatory", "contaminant", "material_safety", "confirmed_hazardous_ingredient"}]
        nutrition_flags = [f for f in self.flags if f.type == "nutrition" and f.label in NUTRITION_FLAG_OPTIONS]
        allergen_flags = [f for f in self.flags if f.type == "allergen"]
        ingredient_flags = [f for f in self.flags if f.type == "ingredient_note"]
        
        def render_section(title: str, flags: list[RiskLensFlag]) -> str:
            if not flags: return ""
            chips = "".join(f"<span class='hz-chip {_css_class_for_flag_type(f.type)}'>{html.escape(f.label)}</span>" for f in flags)
            return f"""
            <div class='hz-flag-section'>
              <div class='hz-subtitle'>{html.escape(title)}</div>
              <div class='hz-chip-row'>{chips}</div>
            </div>
            """

        flags_html = ""
        if include_flags:
            flags_html += render_section("Ingredient notes", ingredient_flags)
            flags_html += render_section("Chemical & processing signals", chemical_flags)
            flags_html += render_section("Nutrition notes", nutrition_flags)
            flags_html += render_section("Allergen notes", allergen_flags)

        food_block = (
            "<div class='hz-food-flags'>"
            f"{flags_html}"
            "<div class='hz-footnote'>Informational notes do not affect the A-E RiskLens Score.</div>"
            "</div>"
            if self.isFood and flags_html
            else ""
        )
        
        risk_items = "".join(f"<li>{html.escape(f.label)}</li>" for f in chemical_flags[:5])
        risk_block = (
            f"<div class='hz-risk-signals'><div class='hz-subtitle'>Key risk signals</div><ul>{risk_items}</ul></div>"
            if include_flags and risk_items and not self.isFood
            else ""
        )
        
        segments = "".join(_segment_html(grade, selected=(grade == score)) for grade in ["A", "B", "C", "D", "E"])
        return f"""
<section class="risklens-score-card" aria-label="{html.escape(self.title)}">
  <style>
    @font-face {{
      font-display: swap;
      font-family: "ReferoBase";
      font-style: normal;
      font-weight: 300 900;
      src: url("https://refero.design/static/media/base-variable.7a7678ae49a8b605a15b.woff2") format("woff2");
    }}
    .risklens-score-card {{
      --hz-border: #d8e2ea;
      --hz-soft-border: rgba(30, 90, 122, 0.08);
      --hz-text: #17212b;
      --hz-muted: #5c6b78;
      --hz-card: #ffffff;
      color-scheme: light;
      
      background: var(--hz-card);
      border: 1px solid var(--hz-border);
      border-radius: 32px;
      padding: 24px;
      font-family: "ReferoBase", -apple-system, sans-serif;
      color: var(--hz-text);
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }}
    .hz-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }}
    .hz-title {{
      font-size: 20px;
      font-weight: 800;
      letter-spacing: -0.045em;
      color: #1e5a7a;
    }}
    .hz-grade-pill {{
      border-radius: 999px;
      background: #FEF3C7;
      color: #17212b;
      font-size: 13px;
      font-weight: 700;
      padding: 5px 12px;
    }}
    .hz-bar {{
      display: flex;
      gap: 4px;
      margin-bottom: 8px;
    }}
    .hz-segment {{
      flex: 1;
      height: 48px;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
      opacity: 0.35;
      transition: opacity 0.2s;
    }}
    .hz-segment.hz-selected {{
      opacity: 1;
      box-shadow: inset 0 0 0 2px #ffffff;
    }}
    .hz-letter {{
      font-size: 18px;
      font-weight: 800;
      color: #fff;
    }}
    .hz-segment.hz-selected .hz-letter {{
      width: 32px;
      height: 32px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.25);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.4);
    }}
    .hz-label-row {{
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      font-weight: 600;
      color: var(--hz-muted);
      padding: 0 2px;
      margin-bottom: 20px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .hz-description {{
      font-size: 15px;
      line-height: 1.5;
      color: var(--hz-text);
      margin-bottom: 8px;
      font-weight: 500;
    }}
    .hz-scope-note {{
      color: var(--hz-muted);
      font-size: 13px;
      line-height: 1.45;
      margin-bottom: 20px;
    }}
    .hz-flag-section {{
      margin-top: 18px;
    }}
    .hz-food-flags {{
      margin-top: 18px;
      padding-top: 4px;
      border-top: 1px solid var(--hz-soft-border);
    }}
    .hz-subtitle {{
      font-size: 14px;
      font-weight: 760;
      margin-bottom: 8px;
      color: #1e5a7a;
    }}
    .hz-chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .hz-chip {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 6px 12px;
      font-size: 13px;
      font-weight: 600;
      border: 1px solid transparent;
    }}
    /* Categorical Flag Styles */
    .hz-type-chemical {{ background: #FEF3C7; color: #78350F; border-color: #FCD34D; }}
    .hz-type-nutrition {{ background: #F3F4F6; color: #374151; border-color: #D1D5DB; }}
    .hz-type-allergen {{ background: #F3F0FF; color: #44336B; border-color: #B7A8F5; }}
    .hz-type-ingredient {{ background: #FFF1F5; color: #7F1D1D; border-color: #FDA4AF; }}

    .hz-footnote {{
      margin-top: 14px;
      font-size: 12px;
      color: var(--hz-muted);
      line-height: 1.4;
      font-style: italic;
    }}
    @media (max-width: 520px) {{
      .risklens-score-card {{ padding: 18px 15px; border-radius: 24px; }}
      .hz-header {{ align-items: flex-start; flex-direction: column; gap: 8px; }}
      .hz-segment {{ min-height: 40px; }}
    }}
  </style>
  <div class="hz-header">
    <div class="hz-title">{html.escape(self.title)}</div>
    <div class="hz-grade-pill">Grade {score} - {html.escape(GRADE_META[score]["label"])}</div>
  </div>
  <div class="hz-bar" role="img" aria-label="RiskLens Score {score}">
    {segments}
  </div>
  <div class="hz-label-row">
    <span>Low</span><span>Mild</span><span>Moderate</span><span>High</span><span>Very high</span>
  </div>
  <div class="hz-description">{html.escape(description)}</div>
  <div class="hz-scope-note">{html.escape(SCOPE_NOTE)}</div>
  {risk_block}
  {food_block}
</section>
""".strip()


def normalize_score(score: str | None) -> RiskLensGrade:
    grade = (score or "A").strip().upper()
    return grade if grade in GRADE_META else "A"  # type: ignore[return-value]


def render_risklens_score_html(api_result: dict[str, Any] | None, input_text: str = "") -> str:
    if not api_result:
        return ""
    return _score_bar_from_api_payload(api_result, input_text=input_text).to_html(include_flags=False)


def render_risklens_flags_html(api_result: dict[str, Any] | None, input_text: str = "") -> str:
    if not api_result:
        return ""
    score = _score_bar_from_api_payload(api_result, input_text=input_text)
    
    # Categorical separation for standalone card
    chemical_flags = [f for flag in score.flags if (f := flag) and flag.type in {"chemical_process", "regulatory", "contaminant", "material_safety", "confirmed_hazardous_ingredient"}]
    nutrition_flags = [f for flag in score.flags if (f := flag) and flag.type == "nutrition" and flag.label in NUTRITION_FLAG_OPTIONS]
    allergen_flags = [f for flag in score.flags if (f := flag) and flag.type == "allergen"]
    ingredient_flags = [f for flag in score.flags if (f := flag) and flag.type == "ingredient_note"]

    def render_block(title: str, flags: list[RiskLensFlag]) -> str:
        if not flags: return ""
        chips = "".join(f"<span class='hz-chip {_css_class_for_flag_type(f.type)}'>{html.escape(f.label)}</span>" for f in flags)
        return f"""
        <div class='hz-flag-section'>
          <div class='hz-subtitle'>{html.escape(title)}</div>
          <div class='hz-chip-row'>{chips}</div>
        </div>
        """

    content = ""
    content += render_block("Ingredient notes", ingredient_flags)
    content += render_block("Chemical & processing signals", chemical_flags)
    content += render_block("Nutrition notes", nutrition_flags)
    content += render_block("Allergen notes", allergen_flags)

    if not content:
        return """
<section class="risklens-flags-card">
  <div class="hz-flags-title">RiskLens Flags</div>
  <div class="hz-empty-flags">No additional hazard or food flags were identified from the available input.</div>
</section>
""".strip()
    
    return f"""
<section class="risklens-flags-card">
  <div class="hz-flags-title">RiskLens Flags</div>
  <style>
    .risklens-flags-card {{
      color-scheme: light;
      background: #ffffff;
      border: 1px solid #d8e2ea;
      border-radius: 28px;
      padding: 20px;
      font-family: "ReferoBase", -apple-system, sans-serif;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
      color: #17212b;
    }}
    .hz-flags-title {{
      font-size: 18px;
      font-weight: 800;
      color: #1e5a7a;
      margin-bottom: 16px;
    }}
    .hz-flag-section {{
      margin-bottom: 16px;
    }}
    .hz-subtitle {{
      font-size: 13px;
      font-weight: 700;
      color: #5c6b78;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
    }}
    .hz-chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .hz-chip {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 5px 12px;
      font-size: 13px;
      font-weight: 600;
      border: 1px solid transparent;
    }}
    .hz-type-chemical {{ background: #FEF3C7; color: #78350F; border-color: #FCD34D; }}
    .hz-type-nutrition {{ background: #F3F4F6; color: #374151; border-color: #D1D5DB; }}
    .hz-type-allergen {{ background: #F3F0FF; color: #44336B; border-color: #B7A8F5; }}
    .hz-type-ingredient {{ background: #FFF1F5; color: #7F1D1D; border-color: #FDA4AF; }}
    .hz-footnote {{
      margin-top: 12px;
      font-size: 12px;
      color: #5c6b78;
      font-style: italic;
    }}
  </style>
  {content}
  <div class='hz-footnote'>Informational notes do not affect the A-E RiskLens Score.</div>
</section>
""".strip()


def _css_class_for_flag_type(flag_type: FlagType) -> str:
    if flag_type == "chemical_process":
        return "hz-type-chemical"
    if flag_type in {"regulatory", "contaminant", "material_safety", "confirmed_hazardous_ingredient"}:
        return "hz-type-chemical" # Use chemical pink for all scoring-related hazards as requested
    if flag_type == "nutrition":
        return "hz-type-nutrition"
    if flag_type == "allergen":
        return "hz-type-allergen"
    return "hz-type-ingredient"


def risklens_score_from_api_result(api_result: dict[str, Any], input_text: str = "") -> RiskLensScoreBar:
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
    nutrition_flags = _nutrition_flags(risks, combined_input_text, is_food, category_text)
    flags = _flags_from_risks(risks, is_food=is_food) + _nutrition_note_flags(nutrition_flags)
    scoring_flags = [flag for flag in flags if _flag_affects_score(flag)]
    score = _score_from_flags(scoring_flags)
    risk_signals = _risk_signals_from_flags(scoring_flags)
    return RiskLensScoreBar(
        score=score,
        description=GRADE_META[score]["description"],
        riskSignals=risk_signals,
        isFood=is_food,
        nutritionFlags=nutrition_flags,
        flags=flags,
        totalRiskPoints=round(sum(flag.riskPoints for flag in scoring_flags), 4),
    )


def _score_bar_from_api_payload(api_result: dict[str, Any], input_text: str = "") -> RiskLensScoreBar:
    payload = api_result.get("risklens_score")
    if not isinstance(payload, dict):
        return risklens_score_from_api_result(api_result, input_text=input_text)

    flags: list[RiskLensFlag] = []
    for raw in payload.get("flags", []) or []:
        if not isinstance(raw, dict):
            continue
        flags.append(
            RiskLensFlag(
                label=str(raw.get("label") or ""),
                type=_coerce_flag_type(raw.get("type")),
                severity=_coerce_flag_severity(raw.get("severity")),
                confidence=_coerce_flag_confidence(raw.get("confidence")),
                evidenceSource=_coerce_evidence_source(raw.get("evidence_source")),
                routeRelevance=_coerce_route_relevance(raw.get("route_relevance")),
                exposureLikelihood=_coerce_exposure_likelihood(raw.get("exposure_likelihood")),
                populationFactor=_coerce_population_factor(raw.get("population_factor")),
                scoreImpact=_coerce_score_impact(raw.get("score_impact")),
                riskPoints=float(raw.get("risk_points") or 0.0),
                reason=str(raw.get("reason") or ""),
            )
        )
    score = normalize_score(str(payload.get("score") or "A"))
    return RiskLensScoreBar(
        score=score,
        title=str(payload.get("title") or "RiskLens Score"),
        description=str(payload.get("description") or GRADE_META[score]["description"]),
        riskSignals=[str(item) for item in payload.get("risk_signals", []) or []],
        isFood=bool(payload.get("is_food", False)),
        nutritionFlags=[str(item) for item in payload.get("nutrition_flags", []) or []],
        flags=flags,
        totalRiskPoints=float(payload.get("total_risk_points") or 0.0),
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


def nutrition_score_from_text(text: str) -> RiskLensScoreBar | None:
    facts = _parse_nutrition_facts(text)
    if not facts:
        # Check if we at least saw the words "nutrition facts"
        if re.search(r"(?i)nutrition facts", text):
            return RiskLensScoreBar(
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

    grades: list[RiskLensGrade] = ["A", "B", "C", "D", "E"]
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

    return RiskLensScoreBar(
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


def _score_from_flags(flags: list[RiskLensFlag]) -> RiskLensGrade:
    active_flags = [flag for flag in flags if _flag_affects_score(flag)]
    total_points = sum(flag.riskPoints for flag in active_flags)
    if total_points <= 0.75:
        score: RiskLensGrade = "A"
    elif total_points <= 1.75:
        score = "B"
    elif total_points <= 3.0:
        score = "C"
    elif total_points <= 4.5:
        score = "D"
    else:
        score = "E"

    if not active_flags:
        return score

    low_impact_flags = [flag for flag in active_flags if flag.scoreImpact == "low"]
    medium_impact_flags = [flag for flag in active_flags if flag.scoreImpact == "medium"]
    high_impact_flags = [flag for flag in active_flags if flag.scoreImpact == "high"]
    if any(flag.evidenceSource in {"lab_result", "recall_or_enforcement"} for flag in active_flags):
        return _max_grade(score, "E")
    if len(high_impact_flags) >= 2:
        return _max_grade(score, "E")
    if high_impact_flags:
        return _max_grade(score, "D")
    if medium_impact_flags or len(low_impact_flags) >= 2:
        return _max_grade(score, "C")
    if low_impact_flags:
        return _max_grade(score, "B")
    return _max_grade(score, "B")


def _flag_impact_rank(flag: RiskLensFlag) -> int:
    return {"none": 0, "low": 1, "medium": 2, "high": 3}.get(flag.scoreImpact, 0)


def _flag_affects_score(flag: RiskLensFlag) -> bool:
    return flag.type in SCORE_AFFECTING_FLAG_TYPES and flag.riskPoints > 0


def _max_grade(left: RiskLensGrade, right: RiskLensGrade) -> RiskLensGrade:
    grades: list[RiskLensGrade] = ["A", "B", "C", "D", "E"]
    return grades[max(grades.index(left), grades.index(right))]


def _risk_signals_from_flags(flags: list[RiskLensFlag]) -> list[str]:
    ranked = sorted(flags, key=lambda flag: (flag.riskPoints, _flag_impact_rank(flag)), reverse=True)
    return [flag.label for flag in ranked[:5] if flag.label.strip()]


def _nutrition_flags(risks: list[dict[str, Any]], input_text: str, is_food: bool, category_text: str = "") -> list[str]:
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
    if _is_food_category(category_text) and re.search(r"\b(artificial\s+color|fd&c|red\s+\d+|yellow\s+\d+|blue\s+\d+|preservative|corn\s+syrup|hydrogenated|modified\s+starch)\b", text):
        flags.append("Ultra-processed")
    return list(dict.fromkeys(flags))


def _is_added_sugar_risk(risk: dict[str, Any]) -> bool:
    text = _norm(" ".join(str(risk.get(key) or "") for key in ["chemical_name", "evidence_from_product"]))
    return "added sugars" in text or "corn syrup" in text or "high-fructose" in text


def _is_food_category(category: str) -> bool:
    if not category:
        return False
    text = _norm(category)
    non_food_terms = [
        "cosmetic",
        "personal care",
        "toy",
        "child care",
        "furniture",
        "building",
        "textile",
        "apparel",
        "electronics",
        "household",
        "cleaning",
        "packaging",
        "food_contact",
        "children_products",
    ]
    if any(term in text for term in non_food_terms):
        return False
    food_terms = [
        "food",
        "snack",
        "cookie",
        "cookies",
        "cracker",
        "chips",
        "candy",
        "beverage",
        "drink",
        "cereal",
        "bakery",
        "bread",
        "meal",
        "soup",
        "sauce",
        "dessert",
        "sweet",
        "baked_goods",
        "frozen_food",
        "processed_meat",
        "raw_meat",
        "ingestible_food_matrix",
        "powdered_or_capsule_form",
    ]
    return any(term in text for term in food_terms)


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


def _flags_from_risks(risks: list[dict[str, Any]], *, is_food: bool) -> list[RiskLensFlag]:
    flags: list[RiskLensFlag] = []
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
        score_impact = _score_impact_for_flag(risk, flag_type, risk_points)
        label = _flag_label(risk)
        reason = str(risk.get("consumer_explanation") or risk.get("evidence_from_product") or "").strip()
        flags.append(
            RiskLensFlag(
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


def _nutrition_note_flags(nutrition_flags: list[str]) -> list[RiskLensFlag]:
    return [
        RiskLensFlag(
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
    flag_type = _norm(risk.get("signal_type"))
    
    # Systemic Fidelity Uplift for Regulatory Signals
    # If a signal is regulatory-backed, we treat the confidence as at least 'likely'
    if flag_type == "regulatory" and raw in {"weak", "possible", "low", ""}:
        return "likely"
        
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
    flag_type = _norm(risk.get("signal_type"))
    
    # Systemic Fidelity Uplift for Regulatory Signals
    # If it is a regulatory signal, promote theoretical/inferred exposure to direct
    if flag_type == "regulatory" and explicit in {"theoretical", "inferred", ""}:
        return "direct_unknown_dose"
        
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


def _score_impact_for_flag(risk: dict[str, Any], flag_type: FlagType, points: float) -> FlagScoreImpact:
    if flag_type in NON_SCORING_FLAG_TYPES or points <= 0:
        return "none"
    explicit = _norm(risk.get("score_impact"))
    if explicit in {"none", "low", "medium", "high"}:
        return explicit  # type: ignore[return-value]
    return _score_impact_from_points(points, flag_type)


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _coerce_flag_type(value: Any) -> FlagType:
    normalized = _norm(value)
    valid = SCORE_AFFECTING_FLAG_TYPES | NON_SCORING_FLAG_TYPES
    return normalized if normalized in valid else "general_product_info"  # type: ignore[return-value]


def _coerce_flag_severity(value: Any) -> FlagSeverity:
    normalized = _norm(value)
    valid = {"info", "low", "moderate", "high", "critical"}
    return normalized if normalized in valid else "info"  # type: ignore[return-value]


def _coerce_flag_confidence(value: Any) -> FlagConfidence:
    normalized = _norm(value)
    valid = {"weak", "possible", "likely", "confirmed", "measured"}
    return normalized if normalized in valid else "weak"  # type: ignore[return-value]


def _coerce_evidence_source(value: Any) -> FlagEvidenceSource:
    normalized = _norm(value)
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
    return normalized if normalized in valid else "general_info"  # type: ignore[return-value]


def _coerce_route_relevance(value: Any) -> FlagRouteRelevance:
    normalized = _norm(value)
    valid = {"none", "uncertain", "food_or_oral"}
    return normalized if normalized in valid else "none"  # type: ignore[return-value]


def _coerce_exposure_likelihood(value: Any) -> FlagExposureLikelihood:
    normalized = _norm(value)
    valid = {"theoretical", "inferred", "direct_unknown_dose", "likely_meaningful", "measured"}
    return normalized if normalized in valid else "theoretical"  # type: ignore[return-value]


def _coerce_population_factor(value: Any) -> FlagPopulationFactor:
    normalized = _norm(value)
    valid = {"general_population", "infant_child_pregnancy_targeted"}
    return normalized if normalized in valid else "general_population"  # type: ignore[return-value]


def _coerce_score_impact(value: Any) -> FlagScoreImpact:
    normalized = _norm(value)
    valid = {"none", "low", "medium", "high"}
    return normalized if normalized in valid else "none"  # type: ignore[return-value]
