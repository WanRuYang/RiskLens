from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "product_extraction_gap_analysis"
EXTRACTION_KEYS = [
    "product_identity_score_5",
    "ingredient_extraction_score_5",
    "warning_claim_extraction_score_5",
]


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def row_scores(row: dict[str, Any]) -> dict[str, float]:
    judge = row.get("judge") or {}
    return {key: safe_float(judge.get(key)) for key in EXTRACTION_KEYS}


def extraction_mean(row: dict[str, Any]) -> float:
    scores = row_scores(row)
    return mean(scores.values()) if scores else 0.0


def group_summary(rows: list[dict[str, Any]], group_key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[safe_text(row.get(group_key)) or "unknown"].append(row)

    summary: list[dict[str, Any]] = []
    for label, group_rows in grouped.items():
        item: dict[str, Any] = {"group_key": group_key, "group": label, "case_count": len(group_rows)}
        for key in EXTRACTION_KEYS:
            item[key] = round(mean(safe_float((row.get("judge") or {}).get(key)) for row in group_rows), 4)
        item["extraction_mean"] = round(mean(extraction_mean(row) for row in group_rows), 4)
        item["low_extraction_count"] = sum(1 for row in group_rows if extraction_mean(row) < 3.0)
        summary.append(item)
    return sorted(summary, key=lambda item: (item["extraction_mean"], -item["case_count"]))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def summarize_case(row: dict[str, Any]) -> dict[str, Any]:
    parsed = row.get("candidate_parsed_output") or {}
    ref = row.get("reference_parsed_output") or {}
    scores = row_scores(row)
    return {
        "case_id": row.get("case_id", ""),
        "mode": row.get("mode", ""),
        "source_marketplace": row.get("source_marketplace", ""),
        "segment": row.get("segment", ""),
        "category_group": row.get("category_group", ""),
        "extraction_mean": round(extraction_mean(row), 4),
        **scores,
        "candidate_product_name": parsed.get("product_name", ""),
        "reference_product_name": ref.get("product_name", ""),
        "candidate_ingredient_len": len(safe_text(parsed.get("ingredient_text"))),
        "reference_ingredient_len": len(safe_text(ref.get("ingredient_text"))),
        "candidate_warning_len": len(safe_text(parsed.get("warning_text")) + safe_text(parsed.get("visible_claims"))),
        "reference_warning_len": len(safe_text(ref.get("warning_text")) + safe_text(ref.get("visible_claims"))),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze product-info extraction gaps from benchmark results.")
    parser.add_argument("--results", type=Path, required=True, help="Gemma benchmark JSON/JSONL results.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--tag", default="", help="Optional output tag.")
    parser.add_argument("--worst", type=int, default=30)
    args = parser.parse_args()

    rows = [row for row in load_rows(args.results) if row.get("status") == "ok"]
    if not rows:
        raise RuntimeError(f"No ok rows found in {args.results}")

    tag = args.tag or args.results.parent.name
    output_dir = args.output_dir / tag
    output_dir.mkdir(parents=True, exist_ok=True)

    case_rows = [summarize_case(row) for row in rows]
    worst_rows = sorted(case_rows, key=lambda item: item["extraction_mean"])[: args.worst]
    by_segment = group_summary(rows, "segment")
    by_category_group = group_summary(rows, "category_group")
    by_marketplace = group_summary(rows, "source_marketplace")

    write_csv(output_dir / "case_extraction_scores.csv", case_rows)
    write_csv(output_dir / "worst_extraction_cases.csv", worst_rows)
    write_csv(output_dir / "by_segment.csv", by_segment)
    write_csv(output_dir / "by_category_group.csv", by_category_group)
    write_csv(output_dir / "by_marketplace.csv", by_marketplace)

    overall = {
        "result_path": str(args.results),
        "case_count": len(rows),
        "extraction_mean": round(mean(extraction_mean(row) for row in rows), 4),
        **{key: round(mean(safe_float((row.get("judge") or {}).get(key)) for row in rows), 4) for key in EXTRACTION_KEYS},
    }
    (output_dir / "summary.json").write_text(json.dumps(overall, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Product Extraction Gap Analysis",
        "",
        f"- Results: `{args.results}`",
        f"- Cases: `{overall['case_count']}`",
        f"- Extraction mean: `{overall['extraction_mean']}`",
        f"- Product identity: `{overall['product_identity_score_5']}`",
        f"- Ingredient/material extraction: `{overall['ingredient_extraction_score_5']}`",
        f"- Warning/claim extraction: `{overall['warning_claim_extraction_score_5']}`",
        "",
        "## Weakest Category Groups",
        "",
    ]
    for item in by_category_group[:12]:
        lines.append(
            f"- `{item['group']}`: mean `{item['extraction_mean']}`, cases `{item['case_count']}`, low cases `{item['low_extraction_count']}`"
        )
    lines.extend(["", "## Worst Cases", ""])
    for item in worst_rows[: args.worst]:
        lines.append(
            f"- `{item['case_id']}` `{item['category_group']}` mean `{item['extraction_mean']}`: "
            f"candidate `{item['candidate_product_name']}` vs reference `{item['reference_product_name']}`"
        )
    (output_dir / "extraction_gap_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Output directory: {output_dir}")
    print(json.dumps(overall, indent=2))


if __name__ == "__main__":
    main()
