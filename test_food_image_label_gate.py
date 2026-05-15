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
    _format_consistent_safety_report,
    _format_food_label_request,
    _has_ingredient_evidence,
    _has_nutrition_evidence,
    _is_food_category,
    _missing_food_label_fields,
    SessionState,
)


def test_food_category_image_gate_detects_missing_label_panels() -> None:
    structured = {
        "product_name": "Nutella Biscuits",
        "product_use_category": "baked_goods",
        "ingredient_text": "",
    }
    text = "Nutella biscuits front package"
    assert _is_food_category(structured, text)
    assert _missing_food_label_fields(text, structured) == ["ingredients", "nutrition facts"]


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
    assert "Product / Front Label Text" in structured_text
    assert "nutella" in structured_text.lower()
    assert "### Ingredients" in structured_text
    assert "PALM OIL" in structured_text
    assert "### Nutrition Facts" in structured_text
    assert "Calories 140" in structured_text
    assert "PALM OIL" in cleaned_passage


def test_food_label_request_mentions_hazardly_score_and_food_flags() -> None:
    message = _format_food_label_request(["ingredients", "nutrition facts"], "Nutella Biscuits")
    assert "Hazardly Score" in message
    assert "food flags" in message
    assert "Nutrition Score" not in message
    assert "ingredient" in message.lower()


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
    assert "Acrylamide" in message
    assert "High added sugar" in message
    assert "No specific chemical concerns" not in message
    assert "No regulatory signals were found" not in message


if __name__ == "__main__":
    test_food_category_image_gate_detects_missing_label_panels()
    test_food_label_gate_accepts_ingredients_and_nutrition_facts()
    test_structured_image_ocr_preserves_screenshot_panels()
    test_food_label_request_mentions_hazardly_score_and_food_flags()
    test_consistent_report_lists_name_category_and_acrylamide_signal()
    print("food image label gate: ok")
