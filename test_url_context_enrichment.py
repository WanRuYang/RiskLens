import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_DIR = PROJECT_ROOT / "database"
if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import service
from app_shared import (
    extract_amazon_ingredient_panel_snippet,
    looks_like_food_preview_context,
    normalize_preview_payload,
)
from database_manager import ProductDatabase


def test_food_context_requests_enrichment_when_label_fields_missing():
    context = {
        "product_text": "Nutella Biscuits",
        "category": "Food",
        "ingredients_text": "",
        "nutrition_text": "",
    }
    assert service._context_needs_label_enrichment(context) is True


def test_food_context_does_not_request_enrichment_when_complete():
    context = {
        "product_text": "Nutella Biscuits",
        "category": "Food",
        "ingredients_text": "Wheat flour, sugar, palm oil",
        "nutrition_text": "Nutrition Facts Calories 140 Sodium 60mg Total Sugars 10g",
    }
    assert service._context_needs_label_enrichment(context) is False


def test_label_image_ocr_backfills_missing_fields():
    context = {
        "product_text": "Nutella Biscuits",
        "category": "Food",
        "ingredients_text": "",
        "nutrition_text": "",
    }
    ocr_text = """
    Ingredients
    Wheat flour, sugar, palm oil, hazelnuts, skim milk powder.

    Nutrition Facts
    Serving size 2 cookies
    Calories 140
    Total Fat 7g
    Sodium 60mg
    Total Sugars 10g
    Added Sugars 9g
    Protein 2g
    """
    enriched = service._merge_label_image_ocr(context, ocr_text)
    assert "Wheat flour" in enriched["ingredients_text"]
    assert "Calories 140" in enriched["nutrition_text"]
    assert enriched["label_image_scan_used"] is True


def test_generic_context_keeps_hardgoods_materials_separate_from_food_ingredients():
    html = """
    <html>
      <head>
        <meta property="og:title" content="Back to Life Clear Bottle 24oz" />
        <script type="application/ld+json">
          {
            "@type": "Product",
            "name": "Back to Life Clear Bottle 24oz",
            "category": "Accessories > Water Bottles",
            "material": "Tritan Renew body, polypropylene lid, silicone seal"
          }
        </script>
      </head>
      <body>
        <h1>Back to Life Clear Bottle 24oz</h1>
        <section><h2>Materials</h2><p>Tritan Renew body, polypropylene lid, silicone seal</p></section>
      </body>
    </html>
    """
    context = service._extract_generic_context(
        html,
        "https://shop.lululemon.com/p/water-bottles/Back-to-Life-Clear-Bottle-24oz/_/prod11750701",
    )
    assert "Back to Life Clear Bottle 24oz" in context["product_text"]
    assert context["category"] == "Accessories > Water Bottles"
    assert "Tritan Renew" in context["materials_text"]
    assert context["ingredients_text"] == ""


def test_generic_context_extracts_food_ingredients_and_nutrition_when_available():
    html = """
    <html>
      <head><meta property="og:title" content="Sample Cookies" /></head>
      <body>
        <h1>Sample Cookies</h1>
        Ingredients: Wheat flour, sugar, palm oil, cocoa.
        Nutrition Facts Calories 140 Sodium 60mg Total Sugars 10g Added Sugars 9g Protein 2g
      </body>
    </html>
    """
    context = service._extract_generic_context(html, "https://example.com/snacks/sample-cookies")
    assert "Wheat flour" in context["ingredients_text"]
    assert "Calories 140" in context["nutrition_text"]


def test_water_bottle_url_failure_requests_typed_materials_not_food_ingredients():
    context = {
        "fetch_attempted": True,
        "fetch_success": False,
        "fetch_error": "blocked",
        "normalized_url": "https://shop.lululemon.com/p/water-bottles/example",
        "product_text": "Back to Life Clear Bottle 24oz",
        "category": "Water Bottles",
        "ingredients_text": "",
        "materials_text": "",
        "nutrition_text": "",
        "warning_text": "",
    }
    assessment = service.assess_input_sufficiency(
        input_mode="url",
        product_name="",
        product_page_url=context["normalized_url"],
        raw_ocr_text="",
        ingredients_text="",
        warning_text="",
        url_context=context,
    )
    assert service._looks_like_food_context(context["product_text"], context["category"]) is False
    assert looks_like_food_preview_context(context) is False
    assert assessment["status"] == "needs_better_url"
    assert "material or ingredient list" in assessment["reason"]


def test_amazon_partial_context_uses_browser_retry_when_dropdown_can_fill_ingredients():
    original_fetch = service.fetch_url_html
    original_extract = service._extract_amazon_context
    original_browser = service._browser_fetch_product_page_context
    original_candidates = service.amazon_fetch_candidates
    called = {"browser": False}
    try:
        service.fetch_url_html = lambda url, headers: "<html></html>"
        service.amazon_fetch_candidates = lambda url: [url]
        service._extract_amazon_context = lambda html, url: {
            "product_text": "Sample Amazon Cookies",
            "category": "Food",
            "ingredients_text": "",
            "nutrition_text": "",
            "warning_text": "",
        }

        def _browser(*args, **kwargs):
            called["browser"] = True
            return {
                "fetch_attempted": True,
                "fetch_success": True,
                "product_text": "Sample Amazon Cookies",
                "category": "Food",
                "ingredients_text": "Wheat flour, sugar, palm oil",
                "materials_text": "",
                "nutrition_text": "",
                "warning_text": "",
            }

        service._browser_fetch_product_page_context = _browser
        context = service.fetch_product_page_context("https://www.amazon.com/dp/B000000000")
    finally:
        service.fetch_url_html = original_fetch
        service._extract_amazon_context = original_extract
        service._browser_fetch_product_page_context = original_browser
        service.amazon_fetch_candidates = original_candidates

    assert called["browser"] is True
    assert "Wheat flour" in context["ingredients_text"]


def test_amazon_partial_ingredient_panel_reports_incomplete_snippet():
    preview = normalize_preview_payload(
        "https://www.amazon.com/dp/B0DC7VRV21",
        {
            "product_name": "Original Skittles Fruit Snacks",
            "product_text": "Original Skittles Fruit Snacks",
            "category": "Food",
            "ingredient_panel_found": True,
            "ingredient_panel_text": "5 percent fruit juice concentrate",
        },
        status="success (browser dropdown extractor)",
    )
    assert preview["intake_assessment"]["status"] == "needs_food_ingredients"
    assert "incomplete ingredient snippet" in preview["intake_assessment"]["reason"]


def test_amazon_partial_ingredient_snippet_can_be_detected_from_html():
    html = """
    <div id="important-information">
      <h2>Important Information</h2>
      <div class="content"><span>Ingredients</span> 5 percent fruit juice concentrate</div>
      <div>Legal Disclaimer</div>
    </div>
    """
    assert extract_amazon_ingredient_panel_snippet(html) == "5 percent fruit juice concentrate"


def test_api_sufficiency_reports_partial_ingredient_panel():
    assessment = service.assess_input_sufficiency(
        input_mode="url",
        product_name="Original Skittles Fruit Snacks",
        product_page_url="https://www.amazon.com/dp/B0DC7VRV21",
        raw_ocr_text="",
        ingredients_text="",
        warning_text="",
        url_context={
            "fetch_success": True,
            "product_text": "Original Skittles Fruit Snacks",
            "category": "Food",
            "ingredients_text": "",
            "ingredient_panel_found": True,
            "ingredient_panel_text": "5 percent fruit juice concentrate",
        },
    )
    assert assessment["status"] == "needs_food_ingredients"
    assert "incomplete ingredient snippet" in assessment["reason"]


def test_complete_older_cache_can_be_reused_without_refresh():
    original_db = ProductDatabase
    try:
        class _FakeDb:
            def get_product(self, url):
                return {
                    "product_name": "Nutella Biscuits",
                    "product_text": "Nutella Biscuits",
                    "category": "Food",
                    "ingredients": "Wheat flour, sugar, palm oil",
                    "logic_version": "26.12",
                }

            def save_product(self, *args, **kwargs):
                raise AssertionError("complete older cache should not be refreshed")

        import database_manager
        import app_shared

        database_manager.ProductDatabase = _FakeDb
        preview = app_shared.preview_url("https://www.amazon.com/dp/B0C449R6PX")
    finally:
        database_manager.ProductDatabase = original_db

    assert preview["intake_assessment"]["can_proceed"] is True
    assert preview["url_context"]["ingredients_text"] == "Wheat flour, sugar, palm oil"


if __name__ == "__main__":
    test_food_context_requests_enrichment_when_label_fields_missing()
    test_food_context_does_not_request_enrichment_when_complete()
    test_label_image_ocr_backfills_missing_fields()
    test_generic_context_keeps_hardgoods_materials_separate_from_food_ingredients()
    test_generic_context_extracts_food_ingredients_and_nutrition_when_available()
    test_water_bottle_url_failure_requests_typed_materials_not_food_ingredients()
    test_amazon_partial_context_uses_browser_retry_when_dropdown_can_fill_ingredients()
    test_amazon_partial_ingredient_panel_reports_incomplete_snippet()
    test_amazon_partial_ingredient_snippet_can_be_detected_from_html()
    test_api_sufficiency_reports_partial_ingredient_panel()
    test_complete_older_cache_can_be_reused_without_refresh()
    print("URL context enrichment checks: PASS")
