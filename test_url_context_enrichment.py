import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_DIR = PROJECT_ROOT / "database"
if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import service
from app_shared import looks_like_food_preview_context


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


if __name__ == "__main__":
    test_food_context_requests_enrichment_when_label_fields_missing()
    test_food_context_does_not_request_enrichment_when_complete()
    test_label_image_ocr_backfills_missing_fields()
    test_generic_context_keeps_hardgoods_materials_separate_from_food_ingredients()
    test_generic_context_extracts_food_ingredients_and_nutrition_when_available()
    test_water_bottle_url_failure_requests_typed_materials_not_food_ingredients()
    print("URL context enrichment checks: PASS")
