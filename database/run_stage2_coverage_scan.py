from __future__ import annotations

import argparse
import csv
import json
import urllib.request
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_BENCHMARK_CSV = Path("/Users/adelie/Projects/gemma4good/benchmark_amazon_100.csv")
DEFAULT_API_BASE_URL = "http://127.0.0.1:8010"
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "outputs" / "stage2_coverage_scan"


def post_json(url: str, payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def run_case(api_base_url: str, row: dict[str, str]) -> dict[str, Any]:
    payload = {
        "user_id": "stage2_coverage_scan",
        "session_id": str(uuid.uuid4()),
        "product_name": row.get("amazon_seed_title", ""),
        "product_page_url": "",
        "raw_ocr_text": "",
        "ingredients_text": "",
        "warning_text": "",
        "region": "California, USA",
        "save_to_history": False,
    }
    result = post_json(f"{api_base_url}/analyze-product", payload)
    inferred = result.get("inferred_category", {}) or {}
    rec = result.get("recommendation", {}) or {}
    scope = result.get("evidence_scope_summary", {}) or {}
    matches = result.get("chemical_matches", []) or []
    sources = result.get("concern_sources", []) or []

    return {
        "benchmark_id": row.get("benchmark_id", ""),
        "segment": row.get("segment", ""),
        "category_group": row.get("category_group", ""),
        "source_marketplace": row.get("source_marketplace", ""),
        "product_title": row.get("amazon_seed_title", ""),
        "product_use_category": inferred.get("product_use_category", "unknown"),
        "material_subcategory": inferred.get("material_subcategory", "unknown"),
        "recommendation_bucket": rec.get("recommendation_bucket", ""),
        "recommendation_reason": rec.get("recommendation_reason", ""),
        "direct_chemical_match_count": len(matches),
        "concern_source_count": len(sources),
        "has_category_level_signal_only": bool(scope.get("has_category_level_signal_only")),
        "has_warning_text_signal": bool(scope.get("has_warning_text_signal")),
        "top_chemical_matches": " | ".join(match.get("preferred_name", "") for match in matches[:3]),
        "top_concern_sources": " | ".join(
            f"{src.get('source_authority', '')}:{src.get('jurisdiction', '')}"
            for src in sources[:3]
        ),
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    category_counts = Counter(row["product_use_category"] for row in rows)
    material_counts = Counter(row["material_subcategory"] for row in rows)
    bucket_counts = Counter(row["recommendation_bucket"] for row in rows)
    direct_match_count = sum(1 for row in rows if row["direct_chemical_match_count"] > 0)
    category_only_count = sum(1 for row in rows if row["has_category_level_signal_only"])

    per_group: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["category_group"]].append(row)

    for group, group_rows in grouped.items():
        majority_category = Counter(row["product_use_category"] for row in group_rows).most_common(1)[0][0]
        majority_material = Counter(row["material_subcategory"] for row in group_rows).most_common(1)[0][0]
        per_group[group] = {
            "count": len(group_rows),
            "majority_product_use_category": majority_category,
            "majority_material_subcategory": majority_material,
            "unknown_category_count": sum(1 for row in group_rows if row["product_use_category"] == "unknown"),
            "unknown_material_count": sum(1 for row in group_rows if row["material_subcategory"] == "unknown"),
            "top_recommendation_buckets": Counter(row["recommendation_bucket"] for row in group_rows).most_common(3),
            "example_titles": [row["product_title"] for row in group_rows[:3]],
        }

    return {
        "total_cases": total,
        "known_category_rate": round(sum(1 for row in rows if row["product_use_category"] != "unknown") / total, 4),
        "known_material_rate": round(sum(1 for row in rows if row["material_subcategory"] != "unknown") / total, 4),
        "direct_chemical_match_rate": round(direct_match_count / total, 4),
        "category_level_signal_only_rate": round(category_only_count / total, 4),
        "product_use_category_counts": category_counts.most_common(),
        "material_subcategory_counts": material_counts.most_common(),
        "recommendation_bucket_counts": bucket_counts.most_common(),
        "groups": per_group,
        "unknown_category_examples": [
            {
                "benchmark_id": row["benchmark_id"],
                "category_group": row["category_group"],
                "product_title": row["product_title"],
            }
            for row in rows
            if row["product_use_category"] == "unknown"
        ][:20],
        "unknown_material_examples": [
            {
                "benchmark_id": row["benchmark_id"],
                "category_group": row["category_group"],
                "product_title": row["product_title"],
                "product_use_category": row["product_use_category"],
            }
            for row in rows
            if row["material_subcategory"] == "unknown"
        ][:20],
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Stage 2 Coverage Scan",
        "",
        f"- Total cases: `{summary['total_cases']}`",
        f"- Known category rate: `{summary['known_category_rate']:.2%}`",
        f"- Known material rate: `{summary['known_material_rate']:.2%}`",
        f"- Direct chemical match rate: `{summary['direct_chemical_match_rate']:.2%}`",
        f"- Category-level-only signal rate: `{summary['category_level_signal_only_rate']:.2%}`",
        "",
        "## Product Use Categories",
    ]
    for label, count in summary["product_use_category_counts"]:
        lines.append(f"- `{label}`: {count}")
    lines.extend(["", "## Materials"])
    for label, count in summary["material_subcategory_counts"]:
        lines.append(f"- `{label}`: {count}")
    lines.extend(["", "## Recommendation Buckets"])
    for label, count in summary["recommendation_bucket_counts"]:
        lines.append(f"- `{label}`: {count}")
    lines.extend(["", "## Groups With Most Unknown Categories"])

    unknown_groups = sorted(
        summary["groups"].items(),
        key=lambda item: item[1]["unknown_category_count"],
        reverse=True,
    )[:10]
    for group, info in unknown_groups:
        lines.append(
            f"- `{group}`: unknown category `{info['unknown_category_count']}`, "
            f"unknown material `{info['unknown_material_count']}`, "
            f"majority category `{info['majority_product_use_category']}`, "
            f"majority material `{info['majority_material_subcategory']}`"
        )

    lines.extend(["", "## Sample Unknown Category Cases"])
    for row in summary["unknown_category_examples"]:
        lines.append(
            f"- `{row['benchmark_id']}` `{row['category_group']}`: {row['product_title']}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a 100-case Stage 2 grounded coverage scan.")
    parser.add_argument("--benchmark-csv", type=Path, default=DEFAULT_BENCHMARK_CSV)
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    with args.benchmark_csv.open(encoding="utf-8") as f:
        input_rows = list(csv.DictReader(f))
    if args.limit > 0:
        input_rows = input_rows[: args.limit]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.out_root / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for idx, row in enumerate(input_rows, start=1):
        print(f"[{idx}/{len(input_rows)}] {row.get('benchmark_id')} {row.get('amazon_seed_title', '')[:80]}")
        try:
            results.append(run_case(args.api_base_url, row))
        except Exception as exc:  # pragma: no cover
            results.append(
                {
                    "benchmark_id": row.get("benchmark_id", ""),
                    "segment": row.get("segment", ""),
                    "category_group": row.get("category_group", ""),
                    "source_marketplace": row.get("source_marketplace", ""),
                    "product_title": row.get("amazon_seed_title", ""),
                    "product_use_category": "error",
                    "material_subcategory": "error",
                    "recommendation_bucket": "error",
                    "recommendation_reason": str(exc),
                    "direct_chemical_match_count": 0,
                    "concern_source_count": 0,
                    "has_category_level_signal_only": False,
                    "has_warning_text_signal": False,
                    "top_chemical_matches": "",
                    "top_concern_sources": "",
                }
            )

    summary = build_summary(results)
    write_csv(out_dir / "coverage_results.csv", results)
    (out_dir / "coverage_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_report(out_dir / "coverage_report.md", summary)

    print(json.dumps(summary, indent=2))
    print(f"Saved coverage scan to {out_dir}")


if __name__ == "__main__":
    main()
