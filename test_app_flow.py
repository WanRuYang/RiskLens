import json
from pathlib import Path

import app


PROJECT_ROOT = Path(__file__).resolve().parent
REQUIRED_PAYLOAD_KEYS = {
    "product_name",
    "product_page_url",
    "raw_ocr_text",
    "ingredient_text",
    "warning_text",
    "safety_caution_text",
    "category_clues",
    "region",
    "input_mode",
    "user_question",
}
REQUIRED_ENVELOPE_KEYS = {"user_id", "session_id", "payload", "stage2", "review", "api_payload"}
REQUIRED_STAGE2_KEYS = {"product_use_category", "material_or_form", "information_priority", "confidence_notes"}
REQUIRED_REVIEW_KEYS = {"user_corrected_text", "user_corrected_category", "queue_for_review", "review_notes", "review_reasons"}
REQUIRED_API_KEYS = {"user_id", "session_id", "product_name", "product_page_url", "raw_ocr_text", "ingredients_text", "warning_text", "region", "input_mode", "save_to_history"}


def assert_has_keys(name: str, obj: dict, required: set[str]) -> None:
    missing = sorted(required - set(obj.keys()))
    if missing:
        raise AssertionError(f"{name} missing keys: {missing}")


def main() -> None:
    sample_images = [
        str(PROJECT_ROOT / "benchmark_images" / "amazon_nonfood_img_035" / "front.png"),
        str(PROJECT_ROOT / "benchmark_images" / "amazon_nonfood_img_035" / "ingredients.png"),
        str(PROJECT_ROOT / "benchmark_images" / "amazon_nonfood_img_035" / "warning.png"),
    ]
    report, debug_json = app.analyze_product(
        sample_images,
        user_id="app_test_user",
        region_label="California, USA",
        product_page_url="https://www.amazon.com/ProtectME-Fabric-Protector-Stain-Resistant/dp/B0TEST1234",
        direct_text="",
        queue_for_review=False,
        review_notes="",
    )

    output_dir = PROJECT_ROOT / "outputs" / "app_flow_test"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "final_report.md").write_text(report, encoding="utf-8")
    (output_dir / "debug_payload.json").write_text(debug_json, encoding="utf-8")

    parsed = json.loads(debug_json)
    envelope = parsed.get("envelope", {})
    payload = envelope.get("payload", {})
    stage2 = envelope.get("stage2", {})
    review = envelope.get("review", {})
    api_payload = envelope.get("api_payload", {})
    api_result = parsed.get("api_result", {})

    assert_has_keys("envelope", envelope, REQUIRED_ENVELOPE_KEYS)
    assert_has_keys("payload", payload, REQUIRED_PAYLOAD_KEYS)
    assert_has_keys("stage2", stage2, REQUIRED_STAGE2_KEYS)
    assert_has_keys("review", review, REQUIRED_REVIEW_KEYS)
    assert_has_keys("api_payload", api_payload, REQUIRED_API_KEYS)

    if payload["input_mode"] != "image":
        raise AssertionError(f"Expected input_mode=image, got {payload['input_mode']!r}")
    if not payload["product_page_url"]:
        raise AssertionError("Expected product_page_url to be preserved in payload")
    if not payload["raw_ocr_text"]:
        raise AssertionError("Expected raw_ocr_text to be non-empty")
    if not api_result.get("inferred_category"):
        raise AssertionError("Expected api_result.inferred_category to exist")
    if not api_result.get("recommendation"):
        raise AssertionError("Expected api_result.recommendation to exist")

    print("Wrote:")
    print(output_dir / "final_report.md")
    print(output_dir / "debug_payload.json")
    print("Contract checks: PASS")
    print("Payload input_mode:", payload["input_mode"])
    print("Recommendation:", api_result["recommendation"])
    print("Inferred category:", api_result["inferred_category"])


if __name__ == "__main__":
    main()
