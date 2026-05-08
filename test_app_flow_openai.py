import json
from pathlib import Path

import app_openai


PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> None:
    sample_images = [
        str(PROJECT_ROOT / "benchmark_images" / "amazon_nonfood_img_035" / "front.png"),
        str(PROJECT_ROOT / "benchmark_images" / "amazon_nonfood_img_035" / "ingredients.png"),
        str(PROJECT_ROOT / "benchmark_images" / "amazon_nonfood_img_035" / "warning.png"),
    ]
    report, debug_json = app_openai.analyze_product(
        sample_images,
        user_id="app_test_user_openai",
        region_label="California, USA",
        product_page_url="https://www.amazon.com/ProtectME-Fabric-Protector-Stain-Resistant/dp/B0TEST1234",
        direct_text="",
        queue_for_review=False,
        review_notes="",
    )

    output_dir = PROJECT_ROOT / "outputs" / "app_flow_test_openai"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "final_report.md").write_text(report, encoding="utf-8")
    (output_dir / "debug_payload.json").write_text(debug_json, encoding="utf-8")

    print("Wrote:")
    print(output_dir / "final_report.md")
    print(output_dir / "debug_payload.json")
    parsed = json.loads(debug_json)
    print("Recommendation:", parsed["api_result"]["recommendation"])
    print("Inferred category:", parsed["api_result"]["inferred_category"])
    print("Model:", parsed["api_result"].get("openai_model"))


if __name__ == "__main__":
    main()
