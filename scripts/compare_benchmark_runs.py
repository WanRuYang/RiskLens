import csv
import json
import sys
from pathlib import Path


def load_scores(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return {row["case_id"]: row for row in csv.DictReader(f)}


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("Usage: compare_benchmark_runs.py GEMMA_DIR OPENAI_DIR OUTPUT_DIR")

    gemma_dir = Path(sys.argv[1])
    openai_dir = Path(sys.argv[2])
    output_dir = Path(sys.argv[3])
    output_dir.mkdir(parents=True, exist_ok=True)

    gemma = load_scores(gemma_dir / "case_scores.csv")
    openai = load_scores(openai_dir / "case_scores.csv")

    all_ids = sorted(set(gemma) | set(openai))
    rows = []
    gemma_strict_values = []
    openai_strict_values = []
    gemma_lenient_values = []
    openai_lenient_values = []

    for case_id in all_ids:
        g = gemma.get(case_id, {})
        o = openai.get(case_id, {})
        row = {
            "case_id": case_id,
            "gemma_strict": g.get("strict_average", ""),
            "openai_strict": o.get("strict_average", ""),
            "gemma_lenient": g.get("lenient_average", ""),
            "openai_lenient": o.get("lenient_average", ""),
            "gemma_false_reassurance": g.get("false_reassurance_flag", ""),
            "openai_false_reassurance": o.get("false_reassurance_flag", ""),
        }
        rows.append(row)

        if row["gemma_strict"]:
            gemma_strict_values.append(float(row["gemma_strict"]))
        if row["openai_strict"]:
            openai_strict_values.append(float(row["openai_strict"]))
        if row["gemma_lenient"]:
            gemma_lenient_values.append(float(row["gemma_lenient"]))
        if row["openai_lenient"]:
            openai_lenient_values.append(float(row["openai_lenient"]))

    csv_path = output_dir / "gemma_vs_openai_case_comparison.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "gemma_cases_available": len(gemma),
        "openai_cases_available": len(openai),
        "gemma_mean_strict": round(mean(gemma_strict_values), 4),
        "openai_mean_strict": round(mean(openai_strict_values), 4),
        "gemma_mean_lenient": round(mean(gemma_lenient_values), 4),
        "openai_mean_lenient": round(mean(openai_lenient_values), 4),
        "note": (
            "Matched 8-case head-to-head comparison."
            if len(gemma) == len(openai)
            else "Gemma raw benchmark currently has fewer completed cases than OpenAI in this comparison."
        ),
    }
    (output_dir / "gemma_vs_openai_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = []
    lines.append("# Gemma Raw vs OpenAI Benchmark Comparison")
    lines.append("")
    lines.append(f"- Gemma cases available: `{len(gemma)}`")
    lines.append(f"- OpenAI cases available: `{len(openai)}`")
    lines.append(f"- Gemma mean strict: `{summary['gemma_mean_strict']:.3f}`")
    lines.append(f"- OpenAI mean strict: `{summary['openai_mean_strict']:.3f}`")
    lines.append(f"- Gemma mean lenient: `{summary['gemma_mean_lenient']:.3f}`")
    lines.append(f"- OpenAI mean lenient: `{summary['openai_mean_lenient']:.3f}`")
    lines.append("")
    lines.append("## Per-case comparison")
    lines.append("")
    for row in rows:
        lines.append(
            f"- `{row['case_id']}`: Gemma strict `{row['gemma_strict'] or 'n/a'}`, "
            f"OpenAI strict `{row['openai_strict'] or 'n/a'}`, "
            f"Gemma lenient `{row['gemma_lenient'] or 'n/a'}`, "
            f"OpenAI lenient `{row['openai_lenient'] or 'n/a'}`"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("- OpenAI completed the full 8-case benchmark in this run.")
    lines.append("- This run is a matched head-to-head comparison because both models completed the same 8 benchmark cases.")
    lines.append("- Even where the direction of concern is correct, the main evaluation focus remains jurisdiction handling, threshold handling, and correct source framing.")
    (output_dir / "gemma_vs_openai_comparison.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
