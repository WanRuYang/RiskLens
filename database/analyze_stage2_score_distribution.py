from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


RAW_RESULTS = Path("/Users/adelie/Projects/gemma4good/outputs/stage2_text_benchmark/20260504_233022/stage2_results.json")
GROUNDED_RESULTS = Path("/Users/adelie/Projects/gemma4good/outputs/stage2_grounded_benchmark/gemma_20260505_102828/stage2_grounded_results.json")
DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "outputs" / "stage2_score_distribution"


def load_results(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def metric_bundle(row: dict[str, Any]) -> dict[str, float]:
    judge = row.get("openai_judge", {}) or {}
    metrics = {
        "category_identification_score_5": float(judge.get("category_identification_score_5", 0)),
        "risk_response_score_5": float(judge.get("risk_response_score_5", 0)),
        "recommendation_alignment_score_5": float(judge.get("recommendation_alignment_score_5", 0)),
        "source_awareness_score_5": float(judge.get("source_awareness_score_5", 0)),
    }
    if "grounding_fidelity_score_5" in judge:
        metrics["grounding_fidelity_score_5"] = float(judge.get("grounding_fidelity_score_5", 0))
    return metrics


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = sorted({name for row in rows for name in metric_bundle(row)})
    overall: dict[str, Any] = {}
    by_category: dict[str, Any] = {}

    for metric in metrics:
        values = [metric_bundle(row).get(metric, 0.0) for row in rows]
        overall[metric] = {
            "mean": round(sum(values) / len(values), 4),
            "distribution": dict(sorted(Counter(values).items())),
            "low_score_cases": [
                {
                    "case_id": row["case_id"],
                    "category": row["truth"]["product_use_category"],
                    "score": metric_bundle(row).get(metric, 0.0),
                }
                for row in rows
                if metric_bundle(row).get(metric, 0.0) < 5
            ],
        }

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["truth"]["product_use_category"]].append(row)

    for category, cat_rows in grouped.items():
        by_category[category] = {
            metric: {
                "mean": round(sum(metric_bundle(row).get(metric, 0.0) for row in cat_rows) / len(cat_rows), 4),
                "distribution": dict(
                    sorted(Counter(metric_bundle(row).get(metric, 0.0) for row in cat_rows).items())
                ),
            }
            for metric in metrics
        }
        by_category[category]["cases"] = [row["case_id"] for row in cat_rows]

    return {"overall": overall, "by_category": by_category}


def write_report(path: Path, label: str, summary: dict[str, Any]) -> None:
    lines = [f"# {label} Stage 2 Score Distribution", ""]
    lines.append("## Overall")
    for metric, info in summary["overall"].items():
        lines.append(f"- `{metric}` mean: `{info['mean']}`")
        lines.append(f"  distribution: `{info['distribution']}`")
        if info["low_score_cases"]:
            lines.append(
                "  below-5 cases: "
                + ", ".join(
                    f"{row['case_id']} ({row['category']}={row['score']})"
                    for row in info["low_score_cases"]
                )
            )
    lines.append("")
    lines.append("## By Product Use Category")
    for category, metrics in summary["by_category"].items():
        lines.append(f"### `{category}`")
        lines.append(f"- cases: `{', '.join(metrics['cases'])}`")
        for metric, info in metrics.items():
            if metric == "cases":
                continue
            lines.append(f"- `{metric}` mean: `{info['mean']}`, distribution: `{info['distribution']}`")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Stage 2 benchmark score distributions.")
    parser.add_argument("--raw-results", type=Path, default=RAW_RESULTS)
    parser.add_argument("--grounded-results", type=Path, default=GROUNDED_RESULTS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    raw_summary = summarize(load_results(args.raw_results))
    grounded_summary = summarize(load_results(args.grounded_results))

    (args.out_dir / "raw_summary.json").write_text(json.dumps(raw_summary, indent=2), encoding="utf-8")
    (args.out_dir / "grounded_summary.json").write_text(json.dumps(grounded_summary, indent=2), encoding="utf-8")
    write_report(args.out_dir / "raw_report.md", "Raw", raw_summary)
    write_report(args.out_dir / "grounded_report.md", "Grounded", grounded_summary)

    comparison = {
        "raw_results": str(args.raw_results),
        "grounded_results": str(args.grounded_results),
        "raw_summary_path": str(args.out_dir / "raw_summary.json"),
        "grounded_summary_path": str(args.out_dir / "grounded_summary.json"),
    }
    (args.out_dir / "comparison_paths.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
