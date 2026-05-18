import sys
import types


fake_mlx = types.ModuleType("mlx_engine")
fake_mlx.run_classifier_agent = lambda text: {}
fake_mlx.run_feedback_agent = lambda text, context: {}
fake_mlx.run_scope_guard_agent = lambda text: "IN_SCOPE_PRODUCT_SAFETY"
fake_mlx.run_scribe_agent = lambda paths: ""
fake_mlx.verify_category_vlm = lambda category, paths: True
sys.modules.setdefault("mlx_engine", fake_mlx)

from app import (
    _build_structured_image_ocr_text,
    _extract_nutrition_facts_text,
    _format_consistent_safety_report,
    _format_food_label_request,
    _hydrate_structured_from_intake,
    _extract_product_name_from_text,
    _has_ingredient_evidence,
    _has_nutrition_evidence,
    _is_food_category,
    _missing_food_label_fields,
    _prepare_ocr_texts,
    _result_product_name,
    _url_intake_failure_copy,
    SessionState,
)
from app_shared import normalize_preview_payload
from database.service import assess_input_sufficiency


def test_food_category_image_gate_requires_ingredients_but_not_nutrition_for_scoring() -> None:
    structured = {
        "product_name": "Nutella Biscuits",
        "product_use_category": "baked_goods",
        "ingredient_text": "",
    }
    text = "Nutella biscuits front package"
    assert _is_food_category(structured, text)
    assert _missing_food_label_fields(text, structured) == ["ingredients"]


def test_food_label_gate_accepts_ingredients_and_nutrition_facts() -> None:
    structured = {
        "product_name": "Nutella Biscuits",
        "product_use_category": "baked_goods",
        "ingredient_text": "Sugar, palm oil, hazelnuts, skim milk, cocoa, wheat flour",
    }
    text = """
    Ingredients: Sugar, palm oil, hazelnuts, skim milk, cocoa, wheat flour.
    Nutrition Facts
    Calories 140
    Saturated Fat 3g 16%
    Sodium 60mg 3%
    Total Sugars 10g
    Includes Added Sugars 9g 18%
    """
    assert _has_ingredient_evidence(text, structured)
    assert _has_nutrition_evidence(text, structured)
    assert _missing_food_label_fields(text, structured) == []


def test_bilingual_nutrition_panel_counts_as_available() -> None:
    text = """
    Nutrition Facts / Valeur nutritive
    Calories 100
    Fat / Lipides 4.5 g
    Saturated / saturés 1.5 g
    Carbohydrate / Glucides 16 g
    Sugars / Sucres 9 g
    Sodium 85 mg
    Protein / Protéines 1 g
    """
    assert _has_nutrition_evidence(text)
    assert "Calories 100" in _extract_nutrition_facts_text(text)


def test_full_ocr_transcript_is_preserved_for_second_stage_structuring() -> None:
    raw_text = """
    IMAGE 1 OCR:
    Christie
    The Original OREO
    OREO

    IMAGE 2 OCR:
    Nutrition Facts / Valeur nutritive
    Calories 100
    Fat / Lipides 4.5 g
    Sodium 85 mg
    Ingredients: Sugars, wheat flour, modified palm oil.
    """
    transcript, quality_text = _prepare_ocr_texts(raw_text)
    assert "The Original OREO" in transcript
    assert "Nutrition Facts / Valeur nutritive" in transcript
    assert "Ingredients:" in transcript
    assert quality_text


def test_structured_image_ocr_preserves_screenshot_panels() -> None:
    raw_text = """
    nutella
    biscuits
    COOKIES FILLED WITH NUTELLA HAZELNUT SPREAD
    NET WT 9.7 OZ (276g)

    Nutrition Facts
    Servings: 10
    Serv. Size 2 cookies (28g)
    Calories 140
    Total Fat 7g 9%
    Saturated Fat 3g 16%
    Sodium 60mg 3%
    Total Carbohydrates 18g 6%
    Total Sugars 10g
    Includes Added Sugars 9g 18%
    Protein 2g

    Ingredients
    HAZELNUT SPREAD WITH COCOA (SUGAR, PALM OIL, HAZELNUTS, SKIM MILK, COCOA,
    LECITHIN AS EMULSIFIER, VANILLIN AN ARTIFICIAL FLAVOR), WHEAT FLOUR,
    VEGETABLE FATS (PALM, PALM KERNEL), CANE SUGAR, LACTOSE, WHEAT BRAN.
    """
    structured_text, cleaned_passage, _ = _build_structured_image_ocr_text(raw_text)
    assert "OCR Section Roles" not in structured_text
    assert "Use Product / Front Label Text for product identity" not in structured_text
    assert "Product / Front Label Text" in structured_text
    assert "nutella" in structured_text.lower()
    assert "### Ingredients" in structured_text
    assert "PALM OIL" in structured_text
    assert "### Nutrition Facts" in structured_text
    assert "Calories 140" in structured_text
    assert "PALM OIL" in cleaned_passage


def test_intake_evidence_overrides_unsupported_product_guess_and_backfills_food_panels() -> None:
    intake_text = """
    ### Product / Front Label Text
    Christie
    20 PACKS
    The Original OREO
    OREO GOLDEN / OREO DOUBLE STUF

    ### Ingredients
    Ingredients: Sugars (sugar and/or golden sugar, glucose-fructose), wheat flour,
    modified palm oil, vegetable oil, cocoa, corn starch, baking soda, soy lecithin.

    ### Nutrition Facts
    Nutrition Facts / Valeur nutritive
    Calories 100
    Fat / Lipides 4.5 g
    Sodium 85 mg
    Sugars / Sucres 9 g
    Protein / Proteines 1 g
    """
    hydrated = _hydrate_structured_from_intake(
        {
            "product_name": "Hot Chocolate Mix (Likely)",
            "product_use_category": "food",
            "ingredient_text": "",
            "nutrition_text": "",
        },
        intake_text,
    )
    assert "OREO" in hydrated["product_name"]
    assert "modified palm oil" in hydrated["ingredient_text"]
    assert "Calories 100" in hydrated["nutrition_text"]
    assert hydrated["material_subcategory"] == "baked_goods"
    assert hydrated["processing_derivatives"] == "Acrylamide"
    assert _missing_food_label_fields(intake_text, hydrated) == []


def test_internal_ocr_heading_is_not_used_as_product_name() -> None:
    intake_text = """
    ### Image OCR
    ### Product / Front Label Text
    Christie
    The Original OREO
    OREO GOLDEN / OREO DOUBLE STUF

    ### Ingredients
    Ingredients: Sugars, wheat flour, modified palm oil.
    """
    assert _extract_product_name_from_text(intake_text) != "### Image OCR"
    assert "OREO" in _extract_product_name_from_text(intake_text)

    state = SessionState()
    state.confirmed_text = intake_text
    state.confirmed_category = {"product_name": "### Image OCR"}
    state.api_result = {}
    assert "OREO" in _result_product_name(state)


def test_oreo_variety_pack_name_is_normalized_from_front_label_evidence() -> None:
    intake_text = """
    IMAGE 1 OCR:
    Christie
    20 PACKS
    OREO

    IMAGE 2 OCR:
    Nutrition Facts / Valeur nutritive
    Ingredients: Sugars, wheat flour.
    """
    hydrated = _hydrate_structured_from_intake(
        {"product_name": "OPED GOLDEN I OREO DORES", "product_use_category": "food"},
        intake_text,
    )
    assert hydrated["product_name"] == "OREO 20 Packs"


def test_food_label_request_treats_nutrition_as_optional_note() -> None:
    message = _format_food_label_request(["ingredients"], "Nutella Biscuits")
    assert "RiskLens Score" in message
    assert "optional nutrition notes" in message
    assert "do not change the A-E RiskLens Score" in message
    assert "Nutrition Score" not in message
    assert "ingredient" in message.lower()


def test_food_url_gate_requires_ingredients_before_analysis() -> None:
    assessment = assess_input_sufficiency(
        input_mode="url",
        product_name="SKITTLES Original Candy Sharing Size Bag",
        product_page_url="https://www.amazon.com/dp/B07WK9K4KQ",
        raw_ocr_text="",
        ingredients_text="",
        warning_text="",
        url_context={
            "fetch_success": True,
            "normalized_url": "https://www.amazon.com/dp/B07WK9K4KQ",
            "product_text": "SKITTLES Original Candy Sharing Size Bag : Grocery & Gourmet Food",
            "category": "Food",
            "ingredients_text": "",
            "warning_text": "",
        },
    )
    assert assessment["can_proceed"] is False
    assert assessment["status"] == "needs_food_ingredients"
    assert assessment["recommended_next_step"] == "ask_for_ingredient_image_or_paste_text"
    assert "ingredient panel" in assessment["reason"]


def test_food_url_preview_without_ingredients_is_not_ready_for_analysis() -> None:
    preview = normalize_preview_payload(
        "https://www.amazon.com/dp/B07WK9K4KQ",
        {
            "product_name": "SKITTLES Original Candy Sharing Size Bag",
            "product_text": "SKITTLES Original Candy Sharing Size Bag",
            "category": "Food",
            "ingredients_text": "",
        },
        status="success (browser fallback)",
    )
    assessment = preview["intake_assessment"]
    assert assessment["can_proceed"] is False
    assert assessment["status"] == "needs_food_ingredients"
    assert "ingredient" in assessment["reason"].lower()


def test_food_url_missing_ingredients_copy_does_not_ask_for_same_url_again() -> None:
    state = SessionState(input_mode="url", product_link="https://www.amazon.com/dp/B0C449R6PX")
    state.url_preview = {
        "intake_assessment": {
            "status": "needs_food_ingredients",
        }
    }
    heading, reason, next_step = _url_intake_failure_copy(
        state,
        "This appears to be a food product, but the webpage did not provide a readable ingredient list.",
    )
    assert "amazon product page" in heading.lower()
    assert "ingredient panel" in heading.lower()
    assert "do not need to re-enter" in next_step.lower()
    assert "ingredient" in reason.lower()


def test_consistent_report_lists_name_category_and_acrylamide_signal() -> None:
    state = SessionState()
    state.confirmed_text = "Nutella biscuits. Ingredients: wheat flour, sugar, palm oil. Nutrition Facts includes added sugars."
    state.confirmed_category = {
        "product_name": "Nutella Biscuits",
        "product_use_category": "food",
        "material_subcategory": "baked_goods",
    }
    state.api_result = {
        "inferred_category": {"product_use_category": "food", "material_subcategory": "baked_goods"},
        "chemical_matches": [],
        "direct_regulatory_evidence": [],
        "category_level_regulatory_evidence": [],
        "url_context": {"ingredients_text": "wheat flour, sugar, palm oil", "category": "Food"},
    }
    message = _format_consistent_safety_report(state)
    assert "## Product Info" in message
    assert "## Potential Chemical Signals" in message
    assert "## Optional Nutrition Note" in message
    assert "Nutella Biscuits" in message
    assert "food / baked_goods" in message
    assert "Nutrition facts:" not in message
    assert "Acrylamide" in message
    assert "High added sugar" in message
    assert "No specific chemical concerns" not in message
    assert "No regulatory signals were found" not in message


if __name__ == "__main__":
    test_food_category_image_gate_requires_ingredients_but_not_nutrition_for_scoring()
    test_food_label_gate_accepts_ingredients_and_nutrition_facts()
    test_bilingual_nutrition_panel_counts_as_available()
    test_full_ocr_transcript_is_preserved_for_second_stage_structuring()
    test_structured_image_ocr_preserves_screenshot_panels()
    test_intake_evidence_overrides_unsupported_product_guess_and_backfills_food_panels()
    test_internal_ocr_heading_is_not_used_as_product_name()
    test_oreo_variety_pack_name_is_normalized_from_front_label_evidence()
    test_food_label_request_treats_nutrition_as_optional_note()
    test_consistent_report_lists_name_category_and_acrylamide_signal()
    print("food image label gate: ok")
