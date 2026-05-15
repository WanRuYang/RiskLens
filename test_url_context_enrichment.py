import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_DIR = PROJECT_ROOT / "database"
if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))

import service


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


if __name__ == "__main__":
    test_food_context_requests_enrichment_when_label_fields_missing()
    test_food_context_does_not_request_enrichment_when_complete()
    test_label_image_ocr_backfills_missing_fields()
    print("URL context enrichment checks: PASS")
