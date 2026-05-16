import sys
import types


fake_mlx = types.ModuleType("mlx_engine")
fake_mlx.run_classifier_agent = lambda text: {}
fake_mlx.run_scope_guard_agent = lambda text: "IN_SCOPE_PRODUCT_SAFETY"
fake_mlx.run_scribe_agent = lambda paths: ""
fake_mlx.verify_category_vlm = lambda category, paths: True
sys.modules.setdefault("mlx_engine", fake_mlx)

from app import (
    SessionState,
    _clean_display_field_text,
    _clean_product_info_ingredient_text,
    _format_food_report,
    _get_display_ingredients,
    _get_display_nutrition,
)


def test_product_info_hides_no_readable_text_placeholders() -> None:
    assert (
        _clean_display_field_text("Enriched wheat flour, sugar, cocoa butter | PRODUCT:\nNO READABLE TEXT")
        == "Enriched wheat flour, sugar, cocoa butter"
    )
    assert _clean_display_field_text("NUTRITION FACTS:\nNO READABLE TEXT") == ""


def test_product_info_fields_drop_placeholder_blocks() -> None:
    state = SessionState()
    state.confirmed_text = (
        "Ingredients: Enriched wheat flour, sugar, cocoa butter | PRODUCT:\n"
        "NO READABLE TEXT\n\n"
        "Nutrition facts: NUTRITION FACTS:\n"
        "NO READABLE TEXT"
    )
    assert _get_display_ingredients(state) == "Enriched wheat flour, sugar, cocoa butter"
    assert _get_display_nutrition(state) == "Missing"


def test_product_info_ingredients_strip_nutrition_panel_noise() -> None:
    raw = """
    Sugars (sugar and/or golden sugar, glucose-fructose), Wheat flour, vegetable oil,
    cocoa, corn starch, baking soda, salt, soy lecithin.
    Nutrition Facts / Valeur nutritive
    Calories 100
    Fat / Lipides 4.5 g 6%
    Sodium 85 mg 4%
    Sugars / Sucres 9 g 9%
    """
    cleaned = _clean_product_info_ingredient_text(raw)
    assert "Sugars (sugar" in cleaned
    assert "Nutrition Facts" not in cleaned
    assert "Calories" not in cleaned
    assert "85 mg" not in cleaned
    assert "%DV" not in cleaned


def test_food_report_shows_ingredients_without_rendering_raw_nutrition_table() -> None:
    state = SessionState()
    state.confirmed_text = (
        "Nutrition Facts / Valeur nutritive Calories 100 Sodium 85 mg 4% Sugars / Sucres 9 g 9%\n"
        "Ingredients: Wheat flour, sugar, vegetable oil, cocoa, salt."
    )
    state.confirmed_category = {
        "product_name": "OREO cookies",
        "product_use_category": "food",
        "material_subcategory": "baked_goods",
        "ingredient_text": "Wheat flour, sugar, vegetable oil, cocoa, salt.",
        "nutrition_text": "Nutrition Facts / Valeur nutritive Calories 100 Sodium 85 mg 4%",
    }
    report = _format_food_report(
        state,
        {
            "product_summary": {"is_food": True},
            "identified_risks": [],
        },
    )
    assert "Product: **OREO cookies**" in report
    assert "Ingredients:" in report
    assert "Wheat flour, sugar, vegetable oil" in report
    assert "Nutrition facts:" not in report
    assert "Calories 100" not in report
    assert "Sodium 85 mg" not in report


if __name__ == "__main__":
    test_product_info_hides_no_readable_text_placeholders()
    test_product_info_fields_drop_placeholder_blocks()
    test_product_info_ingredients_strip_nutrition_panel_noise()
    test_food_report_shows_ingredients_without_rendering_raw_nutrition_table()
    print("product info display: ok")
