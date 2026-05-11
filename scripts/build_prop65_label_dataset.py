from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROP65_NOTICES = PROJECT_ROOT / "data" / "p65_data" / "processed" / "prop65_60_day_notices_full_merged.csv"
DEFAULT_REGULATORY_EVIDENCE = PROJECT_ROOT / "data" / "app_data" / "regulatory_evidence.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "derived" / "label_datasets"


def norm(text: str | None) -> str:
    clean = (text or "").strip().lower()
    clean = re.sub(r"[\s/_-]+", " ", clean)
    return re.sub(r"\s+", " ", clean).strip()


def has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def split_chemicals(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    # Prop 65 notice chemical strings are noisy; keep comma-containing chemical
    # names intact where possible and only split on stronger separators.
    parts = re.split(r"\s*;\s*|\s+\band\b\s+|\s*,\s+(?=[A-Z][A-Za-z][A-Za-z -]+(?:\(|$))", text)
    cleaned: list[str] = []
    for part in parts:
        item = part.strip(" ,;")
        if item and not re.fullmatch(r"\d+", item):
            cleaned.append(item)
    return cleaned or [text]


def infer_product_category(product_text: str) -> str:
    text = norm(product_text)
    rules = [
        ("food", ["food", "snack", "chips", "coffee", "candy", "chocolate", "cocoa", "cookie", "cracker", "cereal", "rice", "noodle", "sauce", "spice", "tea", "fish", "tuna", "meat", "bread", "toast", "oil", "beverage", "juice"]),
        ("food_contact", ["mug", "cup", "plate", "bowl", "glassware", "cookware", "ceramic", "container", "bottle", "can lining", "food packaging", "wrapper", "takeout", "take out", "popcorn bag"]),
        ("children_products", ["toy", "teether", "child", "children", "baby", "infant", "bib", "stroller"]),
        ("personal_care", ["cosmetic", "lotion", "shampoo", "conditioner", "makeup", "cream", "soap"]),
        ("household_cleaner", ["cleaner", "detergent", "degreaser", "disinfect", "bleach", "spray", "polish"]),
        ("textile_or_soft_goods", ["clothing", "shirt", "pants", "textile", "fabric", "glove", "bag", "purse", "wallet", "vinyl"]),
        ("furniture_or_building", ["furniture", "cabinet", "flooring", "wood", "mattress", "sofa"]),
    ]
    for label, terms in rules:
        if has_any(text, terms):
            return label
    return "unknown"


def infer_exposure_pathway(product_text: str, chemical_text: str, product_category: str) -> tuple[str, str, float]:
    product = norm(product_text)
    chemical = norm(chemical_text)

    if product_category == "food_contact" or has_any(product, ["mug", "cup", "plate", "bowl", "container", "packaging", "wrapper", "bottle", "can", "cookware"]):
        return "food_contact_container", "container or food-contact product description", 0.78

    if "acrylamide" in chemical and has_any(product, ["coffee", "chips", "fries", "cracker", "cookie", "cereal", "toast", "bread", "roasted", "baked", "fried"]):
        return "processing_generated", "acrylamide plus roasted/fried/baked starchy or coffee product", 0.9

    if has_any(chemical, ["benz[a]anthracene", "benzo[a]pyrene", "polycyclic aromatic", "pah"]) and has_any(product, ["smoked", "grilled", "barbecue", "char", "meat", "fish"]):
        return "processing_generated", "PAH signal plus smoked/grilled/charred food product", 0.85

    if has_any(chemical, ["n nitroso", "nitrosamine", "n-nitroso"]) or (
        has_any(product, ["cured", "bacon", "ham", "sausage", "hot dog"]) and has_any(chemical, ["nitrite", "nitrate"])
    ):
        return "processing_generated", "cured or nitrosamine-related food signal", 0.82

    if has_any(chemical, ["arsenic", "cadmium", "lead", "mercury"]) and has_any(product, ["rice", "cocoa", "chocolate", "fish", "tuna", "seaweed"]):
        return "raw_material_contaminant", "food matrix commonly associated with elemental contaminant", 0.82

    if product_category == "food" and has_any(chemical, ["titanium dioxide", "benzoic acid", "sodium benzoate", "potassium benzoate", "bha", "bht", "sulfite", "sulphite"]):
        return "declared_ingredient", "food additive/preservative chemical in food product notice", 0.72

    if product_category == "food":
        return "food_uncertain_pathway", "food product notice without enough text to separate ingredient, processing, or contact pathway", 0.45

    if product_category in {"children_products", "personal_care", "household_cleaner", "textile_or_soft_goods", "furniture_or_building"}:
        return "product_material_or_formula", "non-food product category implies material/formula exposure pathway", 0.65

    return "unknown", "insufficient product description for pathway inference", 0.25


def infer_concern_family(chemical_text: str) -> str:
    chemical = norm(chemical_text)
    mapping = [
        ("phthalates_plasticizers", ["phthalate", "dehp", "dinp", "dbp", "bbp", "didp"]),
        ("heavy_metals", ["lead", "cadmium", "arsenic", "mercury", "chromium"]),
        ("bisphenols", ["bisphenol", "bpa", "bps", "bpf"]),
        ("pfas", ["pfas", "pfoa", "pfos", "fluorinated"]),
        ("heat_generated_contaminants", ["acrylamide", "benz[a]anthracene", "benzo[a]pyrene", "nitroso", "nitrosamine"]),
        ("solvents_vocs", ["toluene", "benzene", "xylene", "formaldehyde", "acetaldehyde"]),
        ("pesticides", ["glyphosate", "chlorpyrifos", "malathion"]),
        ("food_additives", ["titanium dioxide", "benzoic", "sulfite", "bha", "bht"]),
    ]
    for family, terms in mapping:
        if has_any(chemical, terms):
            return family
    return "other_prop65_listed"


def build_prop65_notice_examples(notice_path: Path, limit: int = 0) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    with notice_path.open(encoding="utf-8", errors="ignore") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            product_text = (row.get("source") or "").strip()
            if not product_text:
                continue
            chemicals = split_chemicals(row.get("chemicals", ""))
            if not chemicals:
                continue
            product_category = infer_product_category(product_text)
            for chemical in chemicals:
                pathway, reason, confidence = infer_exposure_pathway(product_text, chemical, product_category)
                examples.append(
                    {
                        "example_id": f"prop65_notice_{row.get('ag_number', '').replace('-', '_')}_{len(examples):07d}",
                        "source_dataset": "ca_prop65_60_day_notices",
                        "ag_number": row.get("ag_number", ""),
                        "date": row.get("date", ""),
                        "product_text": product_text,
                        "chemical_text": chemical,
                        "product_category_label": product_category,
                        "exposure_pathway_label": pathway,
                        "concern_family_label": infer_concern_family(chemical),
                        "label_confidence": confidence,
                        "label_reason": reason,
                        "jurisdiction": "California, USA",
                        "label_source": "weak_supervision_from_prop65_notice_product_description",
                    }
                )
                if limit and len(examples) >= limit:
                    return examples
    return examples


def build_regulatory_label_examples(regulatory_path: Path, limit: int = 0) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    with regulatory_path.open(encoding="utf-8", errors="ignore") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            status = norm(row.get("regulatory_status"))
            if "ban" in status or "prohibit" in status:
                risk_label = "banned_or_prohibited"
            elif "restrict" in status or row.get("threshold_value"):
                risk_label = "restricted_or_thresholded"
            elif "listed" in status or row.get("source_authority") == "OEHHA":
                risk_label = "warning_or_hazard_listed"
            elif "allowed" in status or "author" in status:
                risk_label = "allowed_with_conditions"
            else:
                risk_label = "source_context_only"

            examples.append(
                {
                    "example_id": f"regulatory_label_{len(examples):07d}",
                    "source_dataset": row.get("source_dataset_id", ""),
                    "chemical_text": row.get("preferred_name", ""),
                    "product_category_label": row.get("product_category", ""),
                    "product_scope": row.get("product_scope", ""),
                    "source_authority": row.get("source_authority", ""),
                    "jurisdiction": row.get("country_or_jurisdiction", ""),
                    "regulatory_status": row.get("regulatory_status", ""),
                    "hazard_basis": row.get("hazard_basis", ""),
                    "risk_label": risk_label,
                    "threshold_value": row.get("threshold_value", ""),
                    "threshold_unit": row.get("threshold_unit", ""),
                    "label_source": "regulatory_evidence_table",
                }
            )
            if limit and len(examples) >= limit:
                return examples
    return examples


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def build_product_chemical_linkage(prop65_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in prop65_rows:
        try:
            confidence = float(row.get("label_confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        category = row.get("product_category_label") or "unknown"
        pathway = row.get("exposure_pathway_label") or "unknown"
        family = row.get("concern_family_label") or "other_prop65_listed"
        chemical = row.get("chemical_text") or ""
        product_text = row.get("product_text") or ""
        if confidence < 0.65 or category == "unknown" or pathway == "unknown" or not chemical:
            continue

        key = (category, pathway, family)
        group = groups.setdefault(
            key,
            {
                "product_category_label": category,
                "exposure_pathway_label": pathway,
                "concern_family_label": family,
                "chemical_counts": Counter(),
                "chemical_examples": {},
                "confidence_values": [],
                "example_products": [],
            },
        )
        group["chemical_counts"][chemical] += 1
        group["confidence_values"].append(confidence)
        if chemical not in group["chemical_examples"]:
            group["chemical_examples"][chemical] = product_text
        if product_text and product_text not in group["example_products"] and len(group["example_products"]) < 8:
            group["example_products"].append(product_text)

    linkage_rows: list[dict[str, Any]] = []
    for group in groups.values():
        total = sum(group["chemical_counts"].values())
        top_chemicals = []
        for chemical, count in group["chemical_counts"].most_common(10):
            top_chemicals.append(
                {
                    "chemical_text": chemical,
                    "notice_count": count,
                    "share": round(count / total, 4) if total else 0.0,
                    "example_product": group["chemical_examples"].get(chemical, ""),
                }
            )
        linkage_rows.append(
            {
                "product_category_label": group["product_category_label"],
                "exposure_pathway_label": group["exposure_pathway_label"],
                "concern_family_label": group["concern_family_label"],
                "total_notice_rows": total,
                "mean_label_confidence": round(sum(group["confidence_values"]) / len(group["confidence_values"]), 4),
                "top_chemicals": top_chemicals,
                "example_products": group["example_products"],
                "linkage_source": "prop65_weak_supervision_product_description_to_chemical",
                "usage_caveat": "Candidate association only; not confirmed composition or exposure measurement.",
            }
        )
    linkage_rows.sort(key=lambda item: item["total_notice_rows"], reverse=True)
    return linkage_rows


def write_manifest(path: Path, prop65_rows: list[dict[str, Any]], regulatory_rows: list[dict[str, Any]]) -> None:
    pathway_counts = Counter(row["exposure_pathway_label"] for row in prop65_rows)
    category_counts = Counter(row["product_category_label"] for row in prop65_rows)
    family_counts = Counter(row["concern_family_label"] for row in prop65_rows)
    risk_counts = Counter(row["risk_label"] for row in regulatory_rows)
    lines = [
        "# Weak Label Dataset Manifest",
        "",
        "These datasets are weak-supervision labels for product-to-concern classification. They are not final regulatory truth.",
        "",
        f"- Prop 65 notice examples: `{len(prop65_rows)}`",
        f"- Regulatory/source label examples: `{len(regulatory_rows)}`",
        "",
        "## Prop 65 Product Labels",
        "",
        "Main target columns:",
        "- `product_category_label`",
        "- `exposure_pathway_label`",
        "- `concern_family_label`",
        "- `chemical_text`",
        "- `label_confidence`",
        "",
        f"Pathway counts: `{dict(pathway_counts.most_common(20))}`",
        f"Category counts: `{dict(category_counts.most_common(20))}`",
        f"Concern-family counts: `{dict(family_counts.most_common(20))}`",
        "",
        "## Regulatory Label Examples",
        "",
        "Main target columns:",
        "- `risk_label`",
        "- `source_authority`",
        "- `jurisdiction`",
        "- `regulatory_status`",
        "- `hazard_basis`",
        "",
        f"Risk label counts: `{dict(risk_counts.most_common(20))}`",
        "",
        "## Intended Use",
        "",
        "Use these labels to train or evaluate a compact classifier that predicts product category, exposure pathway, concern family, and source/risk label before Gemma writes the final explanation.",
        "",
        "## Caveats",
        "",
        "- Prop 65 60-day notices are allegations/notice records, not exposure measurements.",
        "- `source` is a product description, not a complete ingredient list.",
        "- Processing-generated and food-contact labels are inferred from product and chemical patterns, so keep `label_confidence` and `label_reason`.",
        "- The app should present these as candidate concerns, not confirmed product composition.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ML-ready weak labels from Prop 65 notices and regulatory evidence.")
    parser.add_argument("--prop65-notices", type=Path, default=DEFAULT_PROP65_NOTICES)
    parser.add_argument("--regulatory-evidence", type=Path, default=DEFAULT_REGULATORY_EVIDENCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    prop65_rows = build_prop65_notice_examples(args.prop65_notices, limit=args.limit)
    regulatory_rows = build_regulatory_label_examples(args.regulatory_evidence, limit=args.limit)
    linkage_rows = build_product_chemical_linkage(prop65_rows)

    write_csv(args.output_dir / "prop65_product_weak_labels.csv", prop65_rows)
    write_jsonl(args.output_dir / "prop65_product_weak_labels.jsonl", prop65_rows)
    write_csv(args.output_dir / "regulatory_source_weak_labels.csv", regulatory_rows)
    write_jsonl(args.output_dir / "regulatory_source_weak_labels.jsonl", regulatory_rows)
    write_jsonl(args.output_dir / "product_chemical_linkage.jsonl", linkage_rows)
    write_json(args.output_dir / "product_chemical_linkage.json", linkage_rows)
    write_manifest(args.output_dir / "label_dataset_manifest.md", prop65_rows, regulatory_rows)

    print(f"Output directory: {args.output_dir}")
    print(f"Prop 65 product labels: {len(prop65_rows)}")
    print(f"Regulatory source labels: {len(regulatory_rows)}")
    print(f"Product chemical linkage groups: {len(linkage_rows)}")


if __name__ == "__main__":
    main()
