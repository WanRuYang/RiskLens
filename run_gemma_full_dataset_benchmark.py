from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

import mlx_vlm

from mlx_engine import (
    _run_classifier_agent_local,
    _run_editor_agent_local,
    _run_scribe_agent_local,
    run_search_agent,
)
from prompt_utils import extract_json_object
from run_openai_pretest import load_openai_api_key


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CASES_PATH = PROJECT_ROOT / "benchmark_ocr_real_cases_v2_openai.json"
DEFAULT_REFERENCE_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "openai_full_dataset_benchmark"
    / "20260510_085902"
    / "openai_full_results.json"
)
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "gemma_full_dataset_benchmark"
MODEL_ID = "mlx-community/gemma-4-e4b-it-4bit"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
SCORE_KEYS = [
    "product_identity_score_5",
    "ingredient_extraction_score_5",
    "warning_claim_extraction_score_5",
    "category_identification_score_5",
    "risk_response_score_5",
    "grounding_against_reference_score_5",
]


def safe_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def response_output_text(data: dict[str, Any]) -> str:
    if data.get("output_text"):
        return safe_text(data["output_text"])
    parts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))
    return "\n".join(part for part in parts if safe_text(part))


def load_reference(path: Path) -> dict[str, dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {safe_text(row.get("case_id")): row for row in rows if safe_text(row.get("case_id"))}


def load_existing_results(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    results: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        case_id = safe_text(row.get("case_id"))
        if case_id:
            results[case_id] = row
    return results


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def raw_prompt(case: dict[str, Any]) -> str:
    context = {
        "source_marketplace": case.get("source_marketplace", ""),
        "segment": case.get("segment", ""),
        "category_group": case.get("category_group", ""),
        "expected_strings": case.get("expected_strings", []),
        "web_ground_truth": case.get("web_ground_truth", {}),
    }
    return f"""
You are Gemma4Good running as a RAW single-pass vision model. Read the product images directly and return ONLY valid JSON with these keys:
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

Rules:
- Do not use retrieval or external databases.
- Do not invent ingredients or warnings. If not visible, say what is missing.
- For food, beverage, supplement, cleaner, laundry, or cosmetic products, prioritize ingredient_text.
- For clothing, furniture, electronics, packaging, and durable goods, prioritize material_or_form.
- risk_response should distinguish direct label evidence from general category concern.
- recommended_user_action must be one of: likely_okay, limit_or_compare, avoid_or_replace, need_more_info.

Metadata context, only for orientation:
{json.dumps(context, ensure_ascii=False, indent=2)}
""".strip()


def run_raw_direct_case(model: Any, processor: Any, case: dict[str, Any], max_images: int) -> tuple[str, dict[str, Any]]:
    image_paths = [path for path in case.get("image_paths", [])[:max_images] if Path(path).exists()]
    content = [{"type": "image"} for _ in image_paths]
    content.append({"type": "text", "text": raw_prompt(case)})
    messages = [{"role": "user", "content": content}]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    image_arg: Any = image_paths if len(image_paths) != 1 else image_paths[0]
    try:
        result = mlx_vlm.generate(model, processor, prompt, image_arg, max_tokens=1400, temperature=0.0)
    except Exception:
        if not image_paths:
            raise
        fallback_messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": raw_prompt(case)}]}]
        fallback_prompt = processor.apply_chat_template(fallback_messages, add_generation_prompt=True, tokenize=False)
        result = mlx_vlm.generate(model, processor, fallback_prompt, image_paths[0], max_tokens=1400, temperature=0.0)
    text = result.text.strip() if hasattr(result, "text") else str(result).strip()
    return text, extract_json_object(text)


def run_current_design_case(case: dict[str, Any], max_images: int) -> tuple[str, dict[str, Any], dict[str, Any]]:
    image_paths = [path for path in case.get("image_paths", [])[:max_images] if Path(path).exists()]
    # The app keeps subprocess isolation for Gradio/MLX stability. The benchmark
    # runs on the main thread, so local calls let us reuse the same MLX model cache.
    ocr_text = _run_scribe_agent_local(image_paths, mode="hybrid")
    structured = _run_classifier_agent_local(ocr_text)
    search_payload = {
        "product_name": structured.get("product_name", ""),
        "ingredient_text": structured.get("ingredient_text", ""),
        "warning_text": structured.get("warning_text", ""),
        "region": "California, USA",
        "web_ground_truth": case.get("web_ground_truth", {}),
    }
    api_result = run_search_agent(search_payload)
    final_answer = _run_editor_agent_local(structured, api_result)
    candidate = dict(structured)
    candidate["risk_response"] = final_answer
    candidate["recommended_user_action"] = (api_result.get("recommendation") or {}).get("action", "")
    candidate["grounded_api_result"] = api_result
    trace = {
        "ocr_text": ocr_text,
        "structured_output": structured,
        "search_payload": search_payload,
        "api_result": api_result,
        "final_answer": final_answer,
    }
    return final_answer, candidate, trace


def judge_prompt(case: dict[str, Any], reference: dict[str, Any], candidate: dict[str, Any], mode: str) -> str:
    ref = reference.get("parsed_output", {})
    metadata = {
        "case_id": case.get("id"),
        "source_marketplace": case.get("source_marketplace"),
        "segment": case.get("segment"),
        "category_group": case.get("category_group"),
        "expected_strings": case.get("expected_strings", []),
    }
    return f"""
You are evaluating Gemma4Good benchmark output against an OpenAI-created reference for the same product images and scraped metadata.

Mode being judged: {mode}

Reference output:
{json.dumps(ref, ensure_ascii=False, indent=2)}

Candidate output:
{json.dumps(candidate, ensure_ascii=False, indent=2)}

Case metadata:
{json.dumps(metadata, ensure_ascii=False, indent=2)}

Return ONLY valid JSON with numeric scores from 0 to 5:
- product_identity_score_5
- ingredient_extraction_score_5
- warning_claim_extraction_score_5
- category_identification_score_5
- risk_response_score_5
- grounding_against_reference_score_5
- short_reason

Scoring rubric:
- 5: matches the reference well and is useful for the app.
- 3: partially correct but misses important details or has weak reasoning.
- 1: mostly wrong, vague, or unsafe for this app.
- 0: unusable, missing, or hallucinated.

Judge the candidate against the reference and expected/reference strings. For current_design, reward grounded caution when it clearly separates label evidence from broader regulatory/category concern. Do not require exact wording.
""".strip()


def call_openai_judge(
    api_key: str,
    model: str,
    case: dict[str, Any],
    reference: dict[str, Any],
    candidate: dict[str, Any],
    mode: str,
) -> tuple[str, dict[str, Any]]:
    payload = {"model": model, "input": judge_prompt(case, reference, candidate, mode)}
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI judge error {exc.code}: {error_body}") from exc
    data = json.loads(body)
    text = response_output_text(data)
    return text, extract_json_object(text)


def write_scoring_method(output_dir: Path, mode: str, judge_model: str, reference_path: Path) -> None:
    lines = [
        "# Gemma Full Dataset Benchmark Scoring Method",
        "",
        f"- Candidate mode: `{mode}`",
        f"- Reference file: `{reference_path}`",
        f"- Judge model: `{judge_model}`",
        "- Score range: `0` to `5`, where `5` is strong/reference-aligned and `0` is unusable.",
        "",
        "## Score Fields",
        "- `product_identity_score_5`: product name/type completeness.",
        "- `ingredient_extraction_score_5`: ingredient or material extraction completeness, based on product type.",
        "- `warning_claim_extraction_score_5`: safety warnings and marketing/label claims captured without junk text.",
        "- `category_identification_score_5`: category suitable for downstream reasoning.",
        "- `risk_response_score_5`: cautious, useful safety reasoning that avoids overclaiming.",
        "- `grounding_against_reference_score_5`: agreement with the OpenAI reference and expected/reference strings.",
        "",
        "## Interpretation",
        "OpenAI is used only as a benchmark/reference judge. It is not part of the production product path. The current-design run is expected to improve grounding and recommendation quality over raw single-pass Gemma, while raw can still expose OCR/vision limits.",
    ]
    (output_dir / "scoring_method.md").write_text("\n".join(lines), encoding="utf-8")


def write_outputs(
    output_dir: Path,
    results: list[dict[str, Any]],
    mode: str,
    judge_model: str,
    cases_path: Path,
    reference_path: Path,
) -> None:
    ok_rows = [row for row in results if row.get("status") == "ok"]
    summary: dict[str, Any] = {
        "benchmark": "gemma_full_dataset_vs_openai_reference",
        "mode": mode,
        "cases_path": str(cases_path),
        "reference_path": str(reference_path),
        "case_count": len(results),
        "completed_count": len(ok_rows),
        "failed_count": len(results) - len(ok_rows),
        "judge_model": judge_model,
        "score_scale": "0-5",
    }
    for key in SCORE_KEYS:
        values = [safe_float(row.get("judge", {}).get(key)) for row in ok_rows]
        summary[f"mean_{key}"] = round(mean(values), 4) if values else 0.0

    (output_dir / "gemma_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "gemma_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with (output_dir / "gemma_scores.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["case_id", "status", "mode", "source_marketplace", "segment", "category_group", *SCORE_KEYS, "short_reason", "error"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in results:
            judge = row.get("judge", {}) if isinstance(row.get("judge"), dict) else {}
            writer.writerow(
                {
                    "case_id": row.get("case_id", ""),
                    "status": row.get("status", ""),
                    "mode": mode,
                    "source_marketplace": row.get("source_marketplace", ""),
                    "segment": row.get("segment", ""),
                    "category_group": row.get("category_group", ""),
                    **{key: judge.get(key, "") for key in SCORE_KEYS},
                    "short_reason": judge.get("short_reason", ""),
                    "error": row.get("error", ""),
                }
            )

    lines = [
        f"# Gemma Full Dataset Benchmark ({mode})",
        "",
        f"- Completed: `{summary['completed_count']}/{summary['case_count']}`",
        f"- Failed: `{summary['failed_count']}`",
        f"- Judge: `{judge_model}`",
        "",
        "## Mean Scores",
    ]
    for key in SCORE_KEYS:
        lines.append(f"- `{key}`: `{summary[f'mean_{key}']:.3f}/5`")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "- `gemma_results.jsonl`: checkpointed raw rows",
            "- `gemma_results.json`: full pretty JSON",
            "- `gemma_scores.csv`: flat score table",
            "- `gemma_summary.json`: aggregate metrics",
            "- `scoring_method.md`: rubric",
        ]
    )
    (output_dir / "gemma_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Gemma raw/current-design benchmark on the 300-case dataset and judge against OpenAI reference.")
    parser.add_argument("--mode", choices=["raw", "current_design"], required=True)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--judge-model", default="gpt-4.1-mini")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-images", type=int, default=3)
    parser.add_argument("--resume-dir", type=Path, default=None)
    parser.add_argument("--sleep-sec", type=float, default=0.1)
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if args.limit > 0:
        cases = cases[: args.limit]
    reference = load_reference(args.reference)
    api_key = load_openai_api_key()

    output_dir = args.resume_dir or args.output_root / f"{args.mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)
    write_scoring_method(output_dir, args.mode, args.judge_model, args.reference)
    jsonl_path = output_dir / "gemma_results.jsonl"
    results_by_id = load_existing_results(jsonl_path)

    model = processor = None
    if args.mode == "raw":
        print(f"Loading raw MLX model: {MODEL_ID}", flush=True)
        model, processor = mlx_vlm.load(MODEL_ID)

    for idx, case in enumerate(cases, start=1):
        case_id = safe_text(case.get("id")) or f"case_{idx:04d}"
        if results_by_id.get(case_id, {}).get("status") == "ok":
            print(f"[{idx}/{len(cases)}] {case_id} already complete; skipping", flush=True)
            continue

        print(f"[{idx}/{len(cases)}] {case_id}", flush=True)
        started = time.time()
        try:
            if case_id not in reference:
                raise RuntimeError(f"Missing OpenAI reference for {case_id}")
            if args.mode == "raw":
                assert model is not None and processor is not None
                output_text, candidate = run_raw_direct_case(model, processor, case, args.max_images)
                trace = {"raw_direct_output": output_text}
            else:
                output_text, candidate, trace = run_current_design_case(case, args.max_images)

            judge_raw, judge = call_openai_judge(api_key, args.judge_model, case, reference[case_id], candidate, args.mode)
            row = {
                "case_id": case_id,
                "status": "ok",
                "mode": args.mode,
                "source_marketplace": case.get("source_marketplace", ""),
                "segment": case.get("segment", ""),
                "category_group": case.get("category_group", ""),
                "image_paths": case.get("image_paths", []),
                "candidate_output_text": output_text,
                "candidate_parsed_output": candidate,
                "candidate_trace": trace,
                "reference_parsed_output": reference[case_id].get("parsed_output", {}),
                "judge_raw": judge_raw,
                "judge": judge,
                "duration_sec": round(time.time() - started, 3),
            }
        except Exception as exc:
            row = {
                "case_id": case_id,
                "status": "error",
                "mode": args.mode,
                "source_marketplace": case.get("source_marketplace", ""),
                "segment": case.get("segment", ""),
                "category_group": case.get("category_group", ""),
                "image_paths": case.get("image_paths", []),
                "error": str(exc),
                "duration_sec": round(time.time() - started, 3),
            }
            print(f"  ERROR: {exc}", flush=True)

        results_by_id[case_id] = row
        append_jsonl(jsonl_path, row)
        write_outputs(output_dir, list(results_by_id.values()), args.mode, args.judge_model, args.cases, args.reference)
        if args.sleep_sec > 0:
            time.sleep(args.sleep_sec)

    write_outputs(output_dir, list(results_by_id.values()), args.mode, args.judge_model, args.cases, args.reference)
    print(f"Output directory: {output_dir}", flush=True)
    print(f"Summary: {output_dir / 'gemma_summary.json'}", flush=True)
    print(f"Scores CSV: {output_dir / 'gemma_scores.csv'}", flush=True)


if __name__ == "__main__":
    main()
