import json
from pathlib import Path

import app


PROJECT_ROOT = Path(__file__).resolve().parent


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
    )

    output_dir = PROJECT_ROOT / "outputs" / "app_flow_test"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "final_report.md").write_text(report, encoding="utf-8")
    (output_dir / "debug_payload.json").write_text(debug_json, encoding="utf-8")

    print("Wrote:")
    print(output_dir / "final_report.md")
    print(output_dir / "debug_payload.json")
    parsed = json.loads(debug_json)
    print("Recommendation:", parsed["api_result"]["recommendation"])
    print("Inferred category:", parsed["api_result"]["inferred_category"])


if __name__ == "__main__":
    main()
