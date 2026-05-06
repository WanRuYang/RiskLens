import csv
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
REAL_MANIFEST = PROJECT_ROOT / "benchmark_real_image_manifest.csv"
OUTPUT_JSON = PROJECT_ROOT / "benchmark_ocr_real_cases.json"
MANUAL_EXPECTED = {
    "weee_real_001": ["Calbee", "60g", "のりしお"],
    "weee_real_002": ["ラムネ", "CARBONATED SOFTDRINK", "0.3 L"],
    "weee_real_003": ["Fanale", "ORIGINAL", "www.fanaledrinks.co"],
    "amazon_real_001": ["Premier", "Chocolate", "30g", "11.5 FL OZ", "12 PACK"],
    "amazon_real_002": ["SPARKLING ICE", "BLACK RASPBERRY", "12 PACK", "ZERO SUGAR"],
    "amazon_real_003": ["CELSIUS LIVE FIT", "VARIETY PACK", "12 PACK"],
}


def build_expected_strings(product_title: str) -> list[str]:
    cleaned = re.sub(r"[^\w\s&-]", " ", product_title)
    tokens = [token for token in cleaned.split() if len(token) >= 4]
    phrases: list[str] = []
    if product_title:
        phrases.append(product_title)
    if tokens:
        phrases.append(" ".join(tokens[:2]))
    if len(tokens) >= 4:
        phrases.append(" ".join(tokens[:4]))
    deduped: list[str] = []
    seen = set()
    for item in phrases:
        normalized = item.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(item.strip())
    return deduped


def main() -> None:
    with REAL_MANIFEST.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    cases = []
    for row in rows:
        image_paths = [row["front_image_path"]] if row.get("front_image_path") else []
        if row.get("ingredients_image_path"):
            image_paths.append(row["ingredients_image_path"])
        if row.get("warning_image_path"):
            image_paths.append(row["warning_image_path"])
        case_id = row["case_id"]
        cases.append(
            {
                "id": case_id,
                "image_paths": [str((PROJECT_ROOT / path).resolve()) for path in image_paths],
                "expected_strings": MANUAL_EXPECTED.get(case_id, build_expected_strings(row.get("product_title", ""))),
                "source_marketplace": row.get("source_marketplace", ""),
                "segment": row.get("segment", ""),
                "category_group": row.get("category_group", ""),
            }
        )

    OUTPUT_JSON.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(cases)} real OCR benchmark cases to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
