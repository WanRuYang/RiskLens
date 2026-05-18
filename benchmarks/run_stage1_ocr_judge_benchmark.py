import argparse
import base64
import json
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from run_gemma4_ocr_benchmark import load_cases, load_model, run_ocr_multi, score_case
from run_openai_pretest import load_openai_api_key


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CASES_PATH = PROJECT_ROOT / "benchmark_ocr_real_cases.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "ocr_stage1_openai_judge"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def image_to_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "application/octet-stream")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {}


def build_judge_prompt(case: dict[str, Any], gemma_text: str) -> str:
    expected = case.get("expected_strings", [])
    return f"""
You are judging OCR quality for a consumer-product image extraction benchmark.

Look at the provided image or images yourself, then judge the candidate OCR output from Gemma.

Candidate OCR output:
{gemma_text}

Expected strings for this benchmark case:
{json.dumps(expected, ensure_ascii=False)}

Return ONLY valid JSON with these keys:
- overall_score_5: integer from 0 to 5
- fidelity_score_5: integer from 0 to 5
- completeness_score_5: integer from 0 to 5
- hallucination_score_5: integer from 0 to 5
- expected_string_hits: array of objects with keys expected and hit
- missing_critical_text: boolean
- hallucination_flag: boolean
- short_reason: short string

Scoring guidance:
- Fidelity: how accurately the candidate matches visible text
- Completeness: whether important visible text was captured
- Hallucination: higher is better, meaning fewer invented details
- Overall: overall OCR usefulness for downstream safety reasoning

Important:
- Judge only OCR quality, not regulatory reasoning
- Partial matches count if the visible wording is clearly captured
- Do not punish the candidate for not translating non-English text if the original visible text itself was captured
""".strip()


def call_openai_ocr_judge(
    *,
    api_key: str,
    model: str,
    case: dict[str, Any],
    gemma_text: str,
) -> tuple[str, dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "input_text", "text": build_judge_prompt(case, gemma_text)}]
    for image_path in case.get("image_paths", []):
        content.append(
            {
                "type": "input_image",
                "image_url": image_to_data_url(Path(image_path)),
                "detail": "high",
            }
        )
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": content,
            }
        ],
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
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {error_body}") from exc

    data = json.loads(body)
    output_text = data.get("output_text", "")
    if not output_text:
        output_parts = []
        for item in data.get("output", []):
            for piece in item.get("content", []):
                if piece.get("type") == "output_text":
                    output_parts.append(piece.get("text", ""))
        output_text = "\n".join(part for part in output_parts if part)
    parsed = extract_json_object(output_text)
    return output_text, parsed


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 1 OCR benchmark: Gemma OCR plus OpenAI image-based judging.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--gemma-model-label", default="gemma-4-e4b-it")
    parser.add_argument("--judge-model", default="gpt-4.1-mini")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if args.limit > 0:
        cases = cases[: args.limit]
    if not cases:
        raise RuntimeError("No OCR cases selected.")

    api_key = load_openai_api_key()
    processor, model = load_model()

    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = DEFAULT_OUTPUT_ROOT / run_stamp
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, start=1):
        print(f"[{idx}/{len(cases)}] {case['id']}", flush=True)
        image_paths = [Path(path) for path in case["image_paths"]]
        gemma_text = run_ocr_multi(processor, model, image_paths)
        substring_score = score_case(gemma_text, case.get("expected_strings", []))
        judge_raw, judge = call_openai_ocr_judge(
            api_key=api_key,
            model=args.judge_model,
            case=case,
            gemma_text=gemma_text,
        )
        results.append(
            {
                "case_id": case["id"],
                "image_paths": case["image_paths"],
                "source_marketplace": case.get("source_marketplace"),
                "segment": case.get("segment"),
                "category_group": case.get("category_group"),
                "expected_strings": case.get("expected_strings", []),
                "gemma_text": gemma_text,
                "substring_score": substring_score,
                "openai_judge_raw": judge_raw,
                "openai_judge": judge,
            }
        )

    overall_scores = [safe_float(item["openai_judge"].get("overall_score_5")) for item in results]
    fidelity_scores = [safe_float(item["openai_judge"].get("fidelity_score_5")) for item in results]
    completeness_scores = [safe_float(item["openai_judge"].get("completeness_score_5")) for item in results]
    hallucination_scores = [safe_float(item["openai_judge"].get("hallucination_score_5")) for item in results]
    substring_recalls = [safe_float(item["substring_score"].get("substring_recall")) for item in results]

    summary = {
        "stage": "stage1_ocr",
        "case_count": len(results),
        "gemma_model": args.gemma_model_label,
        "judge_model": args.judge_model,
        "mean_openai_overall_score_5": round(mean(overall_scores), 4),
        "mean_openai_fidelity_score_5": round(mean(fidelity_scores), 4),
        "mean_openai_completeness_score_5": round(mean(completeness_scores), 4),
        "mean_openai_hallucination_score_5": round(mean(hallucination_scores), 4),
        "mean_expected_string_recall": round(mean(substring_recalls), 4),
    }

    (output_dir / "stage1_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "stage1_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report_lines = [
        "# Stage 1 OCR Benchmark",
        "",
        f"- Cases: `{summary['case_count']}`",
        f"- Gemma OCR model: `{summary['gemma_model']}`",
        f"- OpenAI judge model: `{summary['judge_model']}`",
        f"- Mean OpenAI overall score (0-5): `{summary['mean_openai_overall_score_5']:.3f}`",
        f"- Mean OpenAI fidelity score (0-5): `{summary['mean_openai_fidelity_score_5']:.3f}`",
        f"- Mean OpenAI completeness score (0-5): `{summary['mean_openai_completeness_score_5']:.3f}`",
        f"- Mean OpenAI hallucination score (0-5): `{summary['mean_openai_hallucination_score_5']:.3f}`",
        f"- Mean expected-string recall: `{summary['mean_expected_string_recall']:.3f}`",
        "",
        "## Per-case",
    ]
    for item in results:
        judge = item["openai_judge"]
        report_lines.append(
            f"- `{item['case_id']}`: overall `{safe_float(judge.get('overall_score_5')):.1f}/5`, "
            f"fidelity `{safe_float(judge.get('fidelity_score_5')):.1f}/5`, "
            f"completeness `{safe_float(judge.get('completeness_score_5')):.1f}/5`, "
            f"hallucination `{safe_float(judge.get('hallucination_score_5')):.1f}/5`, "
            f"substring recall `{safe_float(item['substring_score'].get('substring_recall')):.3f}`"
        )
    (output_dir / "stage1_report.md").write_text("\n".join(report_lines), encoding="utf-8")

    print(f"Output directory: {output_dir}", flush=True)
    print(f"Mean OpenAI overall score: {summary['mean_openai_overall_score_5']:.3f}/5", flush=True)
    print(f"Mean expected-string recall: {summary['mean_expected_string_recall']:.3f}", flush=True)


if __name__ == "__main__":
    main()
