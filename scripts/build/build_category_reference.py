import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_CSV = PROJECT_ROOT / "data" / "app_data" / "product_risk_mapping.csv"
OUTPUT_JSON = PROJECT_ROOT / "prompts" / "category_reference.json"


DATASET_MAPPINGS = {
    "paper_cup": ("food_contact", "paper", "material_first"),
    "takeaway_container": ("food_contact", "mixed_packaging", "material_first"),
    "waterproof_bib": ("children_products", "pvc_vinyl", "material_first"),
    "mattress_cover": ("household", "coated_textile", "material_first"),
    "shower_curtain": ("household", "pvc_vinyl", "material_first"),
    "sofa_or_cabinet": ("household", "engineered_wood", "material_first"),
    "dyed_textile": ("household", "textile", "material_first"),
    "toy_for_mouthing": ("children_products", "plastic_or_polymer", "material_first"),
    "cosmetic_general": ("personal_care", "cosmetic_formula", "ingredient_first"),
    "prop65_warning_only": ("cross_category", "warning_label_only", "material_first"),
}


MANUAL_ENTRIES = [
    {
        "reference_id": "food_general",
        "product_use_category": "food",
        "material_or_form": "ingestible_food",
        "information_priority": "ingredient_first",
        "keywords": ["jam", "chips", "candy", "snack", "salt", "seasoning", "soda", "drink", "coffee", "tea"],
        "source_basis": "dataset-informed manual reference",
        "notes": "Use ingredient-first reasoning for ordinary foods and beverages.",
    },
    {
        "reference_id": "dietary_supplement",
        "product_use_category": "food",
        "material_or_form": "powdered_or_capsule_form",
        "information_priority": "ingredient_first",
        "keywords": ["supplement", "protein powder", "greens powder", "capsule", "tablet", "gummy vitamin"],
        "source_basis": "dataset-informed manual reference",
        "notes": "Supplements should still follow ingredient-first reasoning even when marketed like wellness products.",
    },
    {
        "reference_id": "food_contact_ceramic",
        "product_use_category": "food_contact",
        "material_or_form": "ceramic",
        "information_priority": "material_first",
        "keywords": ["ceramic mug", "mug", "plate", "bowl", "cup", "porcelain", "stoneware"],
        "source_basis": "dataset-informed manual reference",
        "notes": "Ceramic food-contact products depend heavily on material and decoration clues.",
    },
    {
        "reference_id": "household_cleaner_spray",
        "product_use_category": "household",
        "material_or_form": "cleaner_or_spray_formula",
        "information_priority": "ingredient_first",
        "keywords": ["cleaner", "detergent", "disinfectant", "spray", "fabric protector", "stain resistant", "degreaser", "odor remover"],
        "source_basis": "dataset-informed manual reference",
        "notes": "For cleaners and sprays, ingredients and label handling cautions matter most.",
    },
    {
        "reference_id": "electronics_cable",
        "product_use_category": "electronics",
        "material_or_form": "mixed_material",
        "information_priority": "material_first",
        "keywords": ["cable", "charger", "wire", "cord", "adapter"],
        "source_basis": "dataset-informed manual reference",
        "notes": "Electronics often depend more on accessible material and plastic components than a named ingredient list.",
    },
]


def split_aliases(text: str) -> list[str]:
    return [item.strip() for item in (text or "").split(";") if item.strip()]


def main() -> None:
    rows = list(csv.DictReader(SOURCE_CSV.open("r", encoding="utf-8-sig", newline="")))
    entries = []
    for row in rows:
        product_type_id = row["product_type_id"]
        if product_type_id not in DATASET_MAPPINGS:
            continue
        product_use_category, material_or_form, information_priority = DATASET_MAPPINGS[product_type_id]
        keywords = [row["normalized_product_type"].strip().lower(), product_type_id.replace("_", " ")]
        keywords.extend(alias.lower() for alias in split_aliases(row.get("consumer_aliases", "")))
        entries.append(
            {
                "reference_id": product_type_id,
                "product_use_category": product_use_category,
                "material_or_form": material_or_form,
                "information_priority": information_priority,
                "keywords": sorted(set(keywords)),
                "source_basis": "product_risk_mapping.csv",
                "notes": row.get("warning_guidance_short", "").strip(),
                "what_to_ask_or_scan_next": row.get("what_to_ask_or_scan_next", "").strip(),
            }
        )

    entries.extend(MANUAL_ENTRIES)
    payload = {
        "version": "2026-05-04",
        "description": "Small category reference derived from app data and benchmark-oriented manual additions.",
        "entries": entries,
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(entries)} category reference entries to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
