import csv
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = PROJECT_ROOT / "benchmark_product_image_manifest.csv"
OCR_CASES_PATH = PROJECT_ROOT / "benchmark_ocr_cases.json"
IMAGES_ROOT = PROJECT_ROOT / "benchmark_images"


def load_rows() -> list[dict[str, str]]:
    with MANIFEST_PATH.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def safe_font(size: int):
    for candidate in [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


TITLE_FONT = safe_font(36)
BODY_FONT = safe_font(24)
SMALL_FONT = safe_font(20)


def wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = []
    for word in words:
        trial = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def material_or_ingredient_hint(category: str, title: str, segment: str) -> str:
    title_l = title.lower()
    if segment == "food":
        if "protein" in title_l or "shake" in title_l:
            return "Ingredients: protein blend; milk protein; cocoa or flavoring; gums; vitamins; sweetener."
        if "coffee" in title_l:
            return "Ingredients: coffee beans or coffee extract. Watch for roasting-related concerns or packaging materials."
        if "granola" in title_l or "bar" in title_l or "cereal" in title_l:
            return "Ingredients: oats; sweetener; oils; nuts or chocolate; emulsifiers; natural or artificial flavor."
        if "sunflower" in title_l or "seeds" in title_l:
            return "Ingredients: sunflower seeds; salt; seasoning; flavoring."
        if "ramune" in title_l or "tea" in title_l or "water" in title_l or "energy" in title_l:
            return "Ingredients: water; sweetener; acidulants; flavors; colors; caffeine or tea extracts if applicable."
        if "mochi" in title_l or "ice cream" in title_l:
            return "Ingredients: milk; cream; sugar; stabilizers; starches; flavoring; colors if applicable."
        return "Ingredients: check label text for additives, flavors, colors, preservatives, and processing-related cues."

    if category in {"fabric_cleaners", "laundry_softener"}:
        return "Ingredients or use clues: surfactants; fragrance; solvents; preservatives. CAUTION: Use gloves, avoid inhalation, use with ventilation."
    if category in {"baby_everyday", "baby_walkers"}:
        return "Materials: plastic; textile; foam; adhesives; coatings. Watch for child-use exposure and mouthing context."
    if category in {"clothing_and_wearables"}:
        return "Materials: textile; rubber; foam; dyes; leather or faux leather; coatings or prints."
    if category in {"sports_and_hydration", "kitchen_home"}:
        return "Materials: stainless steel; plastic; silicone; neoprene; electronics components; coatings."
    return "Materials or ingredients: check label for plastics, coatings, dyes, preservatives, or use-safety language."


def warning_hint(category: str, segment: str) -> str:
    if segment == "food":
        return "No marketplace warning captured. If present, scan for Prop 65, California warning text, or additive cautions."
    if category in {"fabric_cleaners", "laundry_softener"}:
        return "CAUTION: Use in a well-ventilated area. Avoid inhalation. Wear gloves. Consider eye protection. Keep away from children."
    return "No marketplace warning captured. If present, scan for Prop 65, material warnings, or child-use cautions."


def make_card(lines: list[str], output_path: Path, *, header: str, accent: tuple[int, int, int]) -> None:
    width, height = 1500, 1000
    image = Image.new("RGB", (width, height), (248, 247, 243))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((40, 40, width - 40, height - 40), radius=24, outline=accent, width=6, fill=(255, 255, 255))
    draw.rectangle((40, 40, width - 40, 130), fill=accent)
    draw.text((70, 65), header, font=TITLE_FONT, fill=(255, 255, 255))

    y = 180
    for block in lines:
        wrapped = wrap(draw, block, BODY_FONT, width - 140)
        for line in wrapped:
            draw.text((70, y), line, font=BODY_FONT, fill=(30, 30, 30))
            y += 38
        y += 18

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def build_assets() -> None:
    rows = load_rows()
    ocr_cases: list[dict[str, object]] = []

    for row in rows:
        case_id = row["case_id"]
        segment = row["segment"]
        category = row["category_group"]
        title = row["product_title"]
        source = row["source_marketplace"]
        product_dir = IMAGES_ROOT / case_id
        front_path = PROJECT_ROOT / row["front_image_path"]
        ingredients_path = PROJECT_ROOT / row["ingredients_image_path"]
        warning_path = PROJECT_ROOT / row["warning_image_path"]

        front_lines = [
            f"Marketplace: {source}",
            f"Segment: {segment}",
            f"Category: {category}",
            f"Product: {title}",
        ]
        ingredient_lines = [
            f"Product: {title}",
            material_or_ingredient_hint(category, title, segment),
        ]
        warning_lines = [
            f"Product: {title}",
            warning_hint(category, segment),
        ]

        make_card(front_lines, front_path, header="Front / Product View", accent=(31, 87, 122))
        make_card(ingredient_lines, ingredients_path, header="Ingredients / Material Clues", accent=(67, 114, 52))
        make_card(warning_lines, warning_path, header="Warning / Safety Text", accent=(150, 78, 43))

        expected_strings = [
            title,
            source,
        ]
        if segment == "food":
            expected_strings.append("Ingredients")
        else:
            expected_strings.append("Materials")
        if category in {"fabric_cleaners", "laundry_softener"}:
            expected_strings.extend(["CAUTION", "Wear gloves", "well-ventilated area"])

        ocr_cases.append(
            {
                "id": case_id,
                "image_path": str(front_path),
                "expected_strings": expected_strings[:6],
            }
        )
        ocr_cases.append(
            {
                "id": f"{case_id}_detail",
                "image_path": str(ingredients_path),
                "expected_strings": [
                    title,
                    "Ingredients" if segment == "food" else "Materials",
                ],
            }
        )
        if category in {"fabric_cleaners", "laundry_softener"}:
            ocr_cases.append(
                {
                    "id": f"{case_id}_warning",
                    "image_path": str(warning_path),
                    "expected_strings": ["CAUTION", "Wear gloves", "well-ventilated area"],
                }
            )

    OCR_CASES_PATH.write_text(json.dumps(ocr_cases, indent=2, ensure_ascii=False))
    print(f"Generated image assets for {len(rows)} benchmark cases.")
    print(f"Wrote OCR cases to {OCR_CASES_PATH}")


if __name__ == "__main__":
    build_assets()
