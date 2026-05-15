import sys
import types


fake_mlx = types.ModuleType("mlx_engine")
fake_mlx.run_classifier_agent = lambda text: {}
fake_mlx.run_scope_guard_agent = lambda text: "IN_SCOPE_PRODUCT_SAFETY"
fake_mlx.run_scribe_agent = lambda paths: ""
fake_mlx.verify_category_vlm = lambda category, paths: True
sys.modules.setdefault("mlx_engine", fake_mlx)

from app import SessionState, _clean_display_field_text, _get_display_ingredients, _get_display_nutrition


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


if __name__ == "__main__":
    test_product_info_hides_no_readable_text_placeholders()
    test_product_info_fields_drop_placeholder_blocks()
    print("product info display: ok")
