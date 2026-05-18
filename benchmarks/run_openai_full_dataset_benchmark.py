from __future__ import annotations

import argparse
import base64
import csv
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from run_openai_pretest import load_openai_api_key


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CASES_PATH = PROJECT_ROOT / "benchmark_ocr_real_cases_v2_openai.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "openai_full_dataset_benchmark"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def safe_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def image_to_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def extract_json_object(text: str) -> dict[str, Any]:
    clean = safe_text(text)
    start = clean.find("{")
    end = clean.rfind("}")
    if start != -1 and end != -1 and end > start:
        clean = clean[start : end + 1]
    try:
        parsed = json.loads(clean)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def response_output_text(data: dict[str, Any]) -> str:
    if data.get("output_text"):
        return safe_text(data["output_text"])
    parts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))
    return "\n".join(part for part in parts if safe_text(part))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_prompt(case: dict[str, Any]) -> str:
    reference = {
        "expected_strings": case.get("expected_strings", []),
        "openai_ground_truth_if_existing": case.get("openai_ground_truth", {}),
        "web_ground_truth": case.get("web_ground_truth", {}),
        "source_marketplace": case.get("source_marketplace", ""),
        "segment": case.get("segment", ""),
        "category_group": case.get("category_group", ""),
    }
    return f"""
You are creating a benchmark reference output for Gemma4Good, a consumer product safety assistant.

Input contains product images and scraped product metadata/reference strings. Use the images first, then use metadata as supporting context if visible text is unclear.

Return ONLY valid JSON with these top-level keys:
- product_name
- product_use_category
- material_or_form
- ingredient_text
- warning_text
- visible_claims
- extracted_text
- missing_information
- risk_response
- recommended_user_action
- eval_scores
- eval_short_reason

For eval_scores, return numeric scores from 0 to 5:
- product_identity_score_5: product name/type completeness
- ingredient_extraction_score_5: ingredient/material extraction completeness
- warning_claim_extraction_score_5: warnings/claims extraction completeness
- category_identification_score_5: product category correctness
- risk_response_score_5: safety reasoning usefulness and calibration
- grounding_against_reference_score_5: agreement with provided expected/reference strings

Rules:
- Do not invent ingredients or warnings. If unknown, leave the field empty and explain what is missing.
- If this is food, beverage, supplement, cosmetic, cleaner, or laundry, prioritize ingredient_text.
- If this is clothing, furniture, electronics, packaging, or other durable goods, prioritize material_or_form.
- risk_response should be concise, cautious, and explicitly distinguish direct label evidence from general category concern.
- recommended_user_action should be one of: likely_okay, limit_or_compare, avoid_or_replace, need_more_info.

Reference metadata for scoring and context:
{json.dumps(reference, ensure_ascii=False, indent=2)}
""".strip()


def call_openai_case(
    *,
    api_key: str,
    model: str,
    case: dict[str, Any],
    max_images: int,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "input_text", "text": build_prompt(case)}]
    missing_images: list[str] = []
    for image_path in case.get("image_paths", [])[:max_images]:
        path = Path(image_path)
        if not path.exists():
            missing_images.append(str(path))
            continue
        content.append({"type": "input_image", "image_url": image_to_data_url(path), "detail": "high"})

    payload = {
        "model": model,
        "input": [{"role": "user", "content": content}],
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            raw_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {error_body}") from exc

    raw_response = json.loads(raw_body)
    output_text = response_output_text(raw_response)
    parsed = extract_json_object(output_text)
    if missing_images:
        parsed.setdefault("missing_information", "")
        parsed["missing_information"] = (safe_text(parsed["missing_information"]) + f" Missing image files: {missing_images}").strip()
    return raw_response, output_text, parsed


def load_existing_results(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        case_id = safe_text(item.get("case_id"))
        if case_id:
            rows[case_id] = item
    return rows


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def write_outputs(output_dir: Path, results: list[dict[str, Any]], model: str, cases_path: Path) -> None:
    parsed_results = [item for item in results if item.get("status") == "ok"]
    score_keys = [
        "product_identity_score_5",
        "ingredient_extraction_score_5",
        "warning_claim_extraction_score_5",
        "category_identification_score_5",
        "risk_response_score_5",
        "grounding_against_reference_score_5",
    ]
    summary: dict[str, Any] = {
        "benchmark": "openai_full_dataset_reference",
        "cases_path": str(cases_path),
        "model": model,
        "case_count": len(results),
        "completed_count": len(parsed_results),
        "failed_count": len(results) - len(parsed_results),
        "score_scale": "0-5",
    }
    for key in score_keys:
        values = [safe_float(item.get("parsed_output", {}).get("eval_scores", {}).get(key)) for item in parsed_results]
        summary[f"mean_{key}"] = round(mean(values), 4) if values else 0.0

    (output_dir / "openai_full_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "openai_full_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = output_dir / "openai_full_scores.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "case_id",
            "status",
            "source_marketplace",
            "segment",
            "category_group",
            "product_name",
            "product_use_category",
            "recommended_user_action",
            *score_keys,
            "eval_short_reason",
            "error",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in results:
            parsed = item.get("parsed_output", {})
            scores = parsed.get("eval_scores", {}) if isinstance(parsed.get("eval_scores"), dict) else {}
            writer.writerow(
                {
                    "case_id": item.get("case_id", ""),
                    "status": item.get("status", ""),
                    "source_marketplace": item.get("source_marketplace", ""),
                    "segment": item.get("segment", ""),
                    "category_group": item.get("category_group", ""),
                    "product_name": parsed.get("product_name", ""),
                    "product_use_category": parsed.get("product_use_category", ""),
                    "recommended_user_action": parsed.get("recommended_user_action", ""),
                    **{key: scores.get(key, "") for key in score_keys},
                    "eval_short_reason": parsed.get("eval_short_reason", ""),
                    "error": item.get("error", ""),
                }
            )

    report_lines = [
        "# OpenAI Full Dataset Benchmark",
        "",
        f"- Cases path: `{cases_path}`",
        f"- Output directory: `{output_dir}`",
        f"- Model: `{model}`",
        f"- Completed: `{summary['completed_count']}/{summary['case_count']}`",
        f"- Failed: `{summary['failed_count']}`",
        "",
        "## Mean Scores",
    ]
    for key in score_keys:
        report_lines.append(f"- `{key}`: `{summary[f'mean_{key}']:.3f}/5`")
    report_lines.extend(["", "## Artifacts", "", "- `openai_full_results.jsonl`: checkpointed per-case raw + parsed output", "- `openai_full_results.json`: full pretty JSON", "- `openai_full_scores.csv`: flat scores for analysis", "- `openai_full_summary.json`: aggregate metrics"])
    (output_dir / "openai_full_report.md").write_text("\n".join(report_lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OpenAI once over the full scraped image/info dataset and save outputs + eval scores.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-images", type=int, default=3)
    parser.add_argument("--sleep-sec", type=float, default=0.2)
    parser.add_argument("--resume-dir", type=Path, default=None)
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if args.limit > 0:
        cases = cases[: args.limit]
    if not isinstance(cases, list) or not cases:
        raise RuntimeError(f"No cases loaded from {args.cases}")

    output_dir = args.resume_dir or args.output_root / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "openai_full_results.jsonl"
    existing = load_existing_results(jsonl_path)

    api_key = load_openai_api_key()
    results_by_id = dict(existing)
    for idx, case in enumerate(cases, start=1):
        case_id = safe_text(case.get("id")) or f"case_{idx:04d}"
        if case_id in results_by_id and results_by_id[case_id].get("status") == "ok":
            print(f"[{idx}/{len(cases)}] {case_id} already complete; skipping", flush=True)
            continue

        print(f"[{idx}/{len(cases)}] {case_id}", flush=True)
        try:
            raw_response, output_text, parsed = call_openai_case(
                api_key=api_key,
                model=args.model,
                case=case,
                max_images=args.max_images,
            )
            result = {
                "case_id": case_id,
                "status": "ok",
                "source_marketplace": case.get("source_marketplace", ""),
                "segment": case.get("segment", ""),
                "category_group": case.get("category_group", ""),
                "image_paths": case.get("image_paths", []),
                "expected_strings": case.get("expected_strings", []),
                "web_ground_truth": case.get("web_ground_truth", {}),
                "openai_output_text": output_text,
                "parsed_output": parsed,
                "openai_raw_response": raw_response,
            }
        except Exception as exc:
            result = {
                "case_id": case_id,
                "status": "error",
                "source_marketplace": case.get("source_marketplace", ""),
                "segment": case.get("segment", ""),
                "category_group": case.get("category_group", ""),
                "image_paths": case.get("image_paths", []),
                "expected_strings": case.get("expected_strings", []),
                "web_ground_truth": case.get("web_ground_truth", {}),
                "error": str(exc),
            }
            print(f"  ERROR: {exc}", flush=True)

        results_by_id[case_id] = result
        append_jsonl(jsonl_path, result)
        write_outputs(output_dir, list(results_by_id.values()), args.model, args.cases)
        if args.sleep_sec > 0:
            time.sleep(args.sleep_sec)

    write_outputs(output_dir, list(results_by_id.values()), args.model, args.cases)
    print(f"Output directory: {output_dir}", flush=True)
    print(f"JSONL: {jsonl_path}", flush=True)
    print(f"Summary: {output_dir / 'openai_full_summary.json'}", flush=True)
    print(f"Scores CSV: {output_dir / 'openai_full_scores.csv'}", flush=True)


if __name__ == "__main__":
    main()
