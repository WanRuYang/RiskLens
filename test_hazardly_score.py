from __future__ import annotations

from hazardly_score import hazardly_score_from_api_result, render_hazardly_flags_html, render_hazardly_score_html
from product_risk_formatter import risk_output_from_api_result
from safety_lookup import SafetyKnowledgeBase


def _api_result(product_name: str, ingredients: str = "", category: str = "food") -> dict:
    result = {
        "inferred_category": {
            "product_use_category": category,
            "material_subcategory": "",
        },
        "chemical_matches": [],
        "direct_regulatory_evidence": [],
        "category_level_regulatory_evidence": [],
        "url_context": {
            "ingredients_text": ingredients,
            "category": category,
        },
    }
    result["structured_risk_output"] = risk_output_from_api_result(
        result,
        product_name=product_name,
        ingredients_text=ingredients,
    )
    return result


def test_corn_syrup_food_flag_does_not_raise_hazardly_score() -> None:
    score = hazardly_score_from_api_result(
        _api_result("Gummy candy", "Corn syrup, sugar, gelatin, natural flavor", "food")
    )
    assert score.score == "A"
    assert "High added sugar" in score.nutritionFlags
    assert score.riskSignals == []
    assert any(
        flag.label == "High added sugar"
        and flag.type == "nutrition"
        and flag.scoreImpact == "none"
        for flag in score.flags
    )


def test_nonstick_ptfe_product_gets_minor_weighted_score_without_food_flags() -> None:
    score = hazardly_score_from_api_result(
        _api_result("Non-stick frying pan with PTFE coating", "", "cookware")
    )
    assert score.score == "B"
    assert score.totalRiskPoints == 1.0
    assert not score.isFood
    assert not score.nutritionFlags
    assert any("PTFE / nonstick coating" in signal for signal in score.riskSignals)


def test_plain_food_without_supported_signals_is_low_concern() -> None:
    score = hazardly_score_from_api_result(
        _api_result("Unsweetened green tea", "Purified water, green tea, vitamin C", "food")
    )
    assert score.score == "A"
    assert score.isFood


def test_clean_fortified_soymilk_stays_grade_a() -> None:
    score = hazardly_score_from_api_result(
        _api_result(
            "Fortified soymilk",
            "Water, soybeans, cane sugar, calcium phosphate, gellan gum, vitamin A, vitamin D",
            "food",
        )
    )
    assert score.score == "A"
    assert "High added sugar" in score.nutritionFlags
    assert not [flag for flag in score.flags if flag.type in {"chemical_process", "regulatory", "contaminant", "material_safety", "confirmed_hazardous_ingredient"} and flag.riskPoints > 0]


def test_generic_cookie_with_acrylamide_only_is_grade_b_not_a() -> None:
    score = hazardly_score_from_api_result(
        _api_result("Generic cookie", "Wheat flour, sugar, vegetable oil, cocoa, salt", "food"),
        input_text="cookies baked sweet snack",
    )
    acrylamide = next(flag for flag in score.flags if flag.label == "Possible acrylamide formation")
    assert acrylamide.type == "chemical_process"
    assert acrylamide.riskPoints == 1.0
    assert acrylamide.scoreImpact == "low"
    assert score.score == "B"


def test_baked_cookie_fallback_surfaces_acrylamide_and_nutrition_flags() -> None:
    api_result = {
        "inferred_category": {
            "product_use_category": "baked_goods",
            "material_subcategory": "",
        },
        "chemical_matches": [],
        "direct_regulatory_evidence": [],
        "category_level_regulatory_evidence": [],
        "url_context": {
            "ingredients_text": "Wheat flour, sugar, palm oil, hazelnuts, skim milk, cocoa",
            "category": "Food",
        },
    }
    score = hazardly_score_from_api_result(api_result, input_text="Nutella biscuits baked cookies")
    assert score.score == "C"
    assert score.totalRiskPoints == 2.0
    assert any("acrylamide" in signal.lower() for signal in score.riskSignals)
    assert "High added sugar" in score.nutritionFlags
    assert "High saturated fat" in score.nutritionFlags
    assert all(
        flag.scoreImpact == "none"
        for flag in score.flags
        if flag.type in {"nutrition", "allergen", "ingredient_note", "serving_size_note", "general_product_info"}
    )


def test_nutrition_label_is_optional_for_hazardly_scoring() -> None:
    score = hazardly_score_from_api_result(
        _api_result("Plain cookies", "Wheat flour, palm oil, sugar", "food"),
        input_text="Plain baked cookies",
    )
    assert score.score == "C"
    assert any(flag.type == "chemical_process" for flag in score.flags)
    assert all(flag.type != "nutrition" or flag.scoreImpact == "none" for flag in score.flags)


def test_measured_food_contaminant_exceedance_can_reach_grade_e() -> None:
    score = hazardly_score_from_api_result(
        {
            "structured_risk_output": {
                "product_summary": {"product_category": "food"},
                "identified_risks": [
                    {
                        "chemical_name": "Lead",
                        "signal_type": "contaminant",
                        "severity": "critical",
                        "confidence_level": "measured",
                        "evidence_source": "lab_result",
                        "route_relevance": "food_or_oral",
                        "exposure_likelihood": "measured",
                        "population_factor": "general_population",
                        "consumer_explanation": "Measured exceedance in a food product.",
                    }
                ],
            },
            "inferred_category": {"product_use_category": "food", "material_subcategory": ""},
            "url_context": {"category": "food"},
        }
    )
    assert score.score == "E"
    assert score.totalRiskPoints == 5.0
    assert score.flags[0].evidenceSource == "lab_result"
    assert score.flags[0].riskPoints == 5.0


def test_oreo_style_product_keeps_nutrition_notes_out_of_score() -> None:
    score = hazardly_score_from_api_result(
        _api_result("Oreo cookies", "Wheat flour, sugar, palm oil, cocoa, soy lecithin, salt", "food"),
        "cookies baked sweet snack Nutrition Facts Total Sugars 9g Sodium 85mg 4% Saturated Fat 1.5g 8%",
    )
    assert score.score == "C"
    assert "High added sugar" in score.nutritionFlags
    assert "High saturated fat" in score.nutritionFlags
    assert "High sodium" not in score.nutritionFlags
    assert all(flag.riskPoints == 0 for flag in score.flags if flag.type == "nutrition")


def test_direct_prop65_product_warning_has_high_grade_floor() -> None:
    score = hazardly_score_from_api_result(
        {
            "structured_risk_output": {
                "product_summary": {"product_category": "food"},
                "identified_risks": [
                    {
                        "chemical_name": "Lead",
                        "signal_type": "regulatory",
                        "severity": "high",
                        "confidence_level": "confirmed",
                        "evidence_source": "product_warning",
                        "route_relevance": "food_or_oral",
                        "exposure_likelihood": "direct_unknown_dose",
                        "population_factor": "general_population",
                        "consumer_explanation": "Direct product-specific Proposition 65 warning.",
                    }
                ],
            },
            "inferred_category": {"product_use_category": "food", "material_subcategory": ""},
            "url_context": {"category": "food"},
        }
    )
    assert score.score == "D"
    assert score.flags[0].type == "regulatory"
    assert score.flags[0].scoreImpact == "high"
    assert score.flags[0].evidenceSource == "product_warning"


def test_db_backed_food_dye_warning_signal_is_not_silently_dropped() -> None:
    kb = SafetyKnowledgeBase()
    red40 = next(
        match
        for match in kb.match_chemicals("Rainbow gummy candy", "Sugar, Red 40 Lake")
        if match.preferred_name == "Allura Red AC"
    )
    api_result = {
        "inferred_category": {"product_use_category": "food", "material_subcategory": ""},
        "chemical_matches": [
            {
                "chemical_id": red40.chemical_id,
                "preferred_name": red40.preferred_name,
                "matched_text": "Red 40 Lake",
            }
        ],
        "direct_regulatory_evidence": kb.evidence_by_chemical_id[red40.chemical_id],
        "category_level_regulatory_evidence": [],
        "url_context": {
            "ingredients_text": "Sugar, corn syrup, Red 40 Lake",
            "category": "food",
        },
    }
    api_result["structured_risk_output"] = risk_output_from_api_result(
        api_result,
        product_name="Rainbow gummy candy",
        ingredients_text="Sugar, corn syrup, Red 40 Lake",
    )
    score = hazardly_score_from_api_result(api_result)
    dye = next(flag for flag in score.flags if "Allura Red" in flag.label)
    assert dye.type == "regulatory"
    assert dye.scoreImpact == "high"
    assert dye.riskPoints > 0
    assert score.score in {"D", "E"}


def test_render_score_panel_omits_nutrition_score_when_table_present() -> None:
    html = render_hazardly_score_html(
        _api_result("Nutella biscuits", "Sugar, palm oil, wheat flour", "food"),
        "Nutrition Facts Calories 140 Sodium 60mg 3% Total Sugars 10g Includes Added Sugars 9g 18% Saturated Fat 3g 16%",
    )
    assert "Hazardly Score" in html
    assert "Nutrition Score" not in html
    assert "Food flags" not in html


def test_render_flags_panel_separates_hazard_and_food_flags() -> None:
    html = render_hazardly_flags_html(
        _api_result("Nutella biscuits", "Sugar, palm oil, wheat flour", "food"),
        "Nutrition Facts Calories 140 Total Sugars 10g Includes Added Sugars 9g 18% Saturated Fat 3g 16%",
    )
    assert "Hazardly Flags" in html
    assert "Chemical / process flags" not in html
    assert "Food flags" not in html
    assert "Chemical &amp; processing signals" in html
    assert "Nutrition notes" in html
    assert "High added sugar" in html


def test_web_renderer_uses_final_backend_score_payload() -> None:
    html = render_hazardly_score_html(
        {
            "hazardly_score": {
                "score": "C",
                "title": "Hazardly Score",
                "description": "backend final score",
                "risk_signals": ["Possible acrylamide formation"],
                "is_food": True,
                "nutrition_flags": [],
                "flags": [
                    {
                        "label": "Possible acrylamide formation",
                        "type": "chemical_process",
                        "severity": "moderate",
                        "confidence": "possible",
                        "evidence_source": "process_inference",
                        "route_relevance": "food_or_oral",
                        "exposure_likelihood": "likely_meaningful",
                        "population_factor": "general_population",
                        "score_impact": "low",
                        "risk_points": 1.0,
                        "reason": "Backend payload.",
                    }
                ],
                "total_risk_points": 1.0,
            }
        }
    )
    assert "Grade C" in html
    assert "backend final score" in html


def test_low_sodium_label_does_not_create_high_sodium_flag() -> None:
    score = hazardly_score_from_api_result(
        _api_result("Oreo cookies", "Sugar, wheat flour, palm oil, salt", "food"),
        "Nutrition Facts Calories 100 Sodium 85mg 4% Total Sugars 9g Saturated Fat 1.5g 8%",
    )
    assert "High sodium" not in score.nutritionFlags


def test_ultra_processed_flag_is_hidden_for_non_food_categories() -> None:
    score = hazardly_score_from_api_result(
        _api_result(
            "Children's craft slime",
            "Water, preservative, modified starch, artificial color",
            "toy / child care product",
        )
    )
    assert "Ultra-processed" not in score.nutritionFlags


def test_ultra_processed_flag_is_hidden_for_food_contact_categories() -> None:
    score = hazardly_score_from_api_result(
        _api_result(
            "Food storage container",
            "Preservative, modified starch, artificial color",
            "food_contact",
        )
    )
    assert "Ultra-processed" not in score.nutritionFlags


if __name__ == "__main__":
    test_corn_syrup_food_flag_does_not_raise_hazardly_score()
    test_nonstick_ptfe_product_gets_minor_weighted_score_without_food_flags()
    test_plain_food_without_supported_signals_is_low_concern()
    test_clean_fortified_soymilk_stays_grade_a()
    test_generic_cookie_with_acrylamide_only_is_grade_b_not_a()
    test_baked_cookie_fallback_surfaces_acrylamide_and_nutrition_flags()
    test_nutrition_label_is_optional_for_hazardly_scoring()
    test_measured_food_contaminant_exceedance_can_reach_grade_e()
    test_oreo_style_product_keeps_nutrition_notes_out_of_score()
    test_direct_prop65_product_warning_has_high_grade_floor()
    test_render_score_panel_omits_nutrition_score_when_table_present()
    test_render_flags_panel_separates_hazard_and_food_flags()
    test_web_renderer_uses_final_backend_score_payload()
    test_low_sodium_label_does_not_create_high_sodium_flag()
    test_ultra_processed_flag_is_hidden_for_non_food_categories()
    test_ultra_processed_flag_is_hidden_for_food_contact_categories()
    print("hazardly score: ok")
