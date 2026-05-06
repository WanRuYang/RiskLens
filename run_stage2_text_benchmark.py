import argparse
import json
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoProcessor

from prompt_utils import format_prompt
from run_gemma4_pretest import load_cases, load_model
from run_openai_pretest import load_openai_api_key


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CASES_PATH = PROJECT_ROOT / "benchmark_cases.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "stage2_text_benchmark"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

STAGE2_TRUTH = {
    "jam_ascorbic_acid": {
        "product_use_category": "food",
        "material_or_form": "spread_or_ingestible_food",
        "information_priority": "ingredient_first",
    },
    "garlic_salt_calcium_phosphate": {
        "product_use_category": "food",
        "material_or_form": "seasoning_powder",
        "information_priority": "ingredient_first",
    },
    "paper_cup_bpa": {
        "product_use_category": "food_contact",
        "material_or_form": "paper",
        "information_priority": "material_first",
    },
    "baby_bib_dehp": {
        "product_use_category": "children_products",
        "material_or_form": "pvc_vinyl",
        "information_priority": "material_first",
    },
    "potato_chips_acrylamide": {
        "product_use_category": "food",
        "material_or_form": "snack_food",
        "information_priority": "ingredient_first",
    },
    "teething_toy_formaldehyde": {
        "product_use_category": "children_products",
        "material_or_form": "plastic_or_polymer",
        "information_priority": "material_first",
    },
    "ceramic_mug_lead": {
        "product_use_category": "food_contact",
        "material_or_form": "ceramic",
        "information_priority": "material_first",
    },
    "candy_titanium_dioxide": {
        "product_use_category": "food",
        "material_or_form": "confectionery",
        "information_priority": "ingredient_first",
    },
}

def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
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


def build_stage2_input(case: Any) -> dict[str, str]:
    observed_signal = case.observed_signal or ""
    ingredient_text = ""
    warning_text = ""
    category_clues = ""

    lowered = observed_signal.lower()
    if lowered.startswith("ingredient listed:"):
        ingredient_text = observed_signal.split(":", 1)[1].strip()
    elif lowered.startswith("material/ingredient clue:"):
        clue = observed_signal.split(":", 1)[1].strip()
        ingredient_text = clue
        category_clues = clue
    elif lowered.startswith("concern term:"):
        clue = observed_signal.split(":", 1)[1].strip()
        ingredient_text = clue
        warning_text = clue
    else:
        category_clues = observed_signal

    return {
        "product_name": case.product_name,
        "ingredient_text": ingredient_text,
        "warning_text": warning_text,
        "category_clues": category_clues,
        "region": case.region,
        "user_question": case.user_question,
    }


def build_stage2_prompt(case: Any, normalized_input: dict[str, str]) -> str:
    instructions = """
Return ONLY valid JSON with these keys:
- reference_id
- product_use_category
- material_or_form
- information_priority
- recommendation_bucket
- occasional_use_view
- source_types_to_check
- missing_information_to_request
- risk_response

Rules:
- product_use_category should be a short label such as food, food_contact, household, children_products, personal_care, bags_accessories, electronics, or unknown.
- material_or_form should be a short label.
- information_priority must be exactly one of:
  - ingredient_first
  - material_first
- If this is food, drink, supplement, or a household cleaner/spray, ingredient_first is usually the correct choice.
- Otherwise material_first is usually the correct choice.
- recommendation_bucket should be one of:
  - higher_concern
  - context_dependent
  - likely_lower_concern
  - insufficient_info
- occasional_use_view should be one of:
  - avoid
  - limit
  - likely_okay
  - insufficient_info
- source_types_to_check should be an array of at most 4 short strings.
- missing_information_to_request should be a short string describing what extra info would help.
- risk_response should be 2 to 4 sentences and should stay cautious.
"""
    payload = json.dumps(normalized_input, ensure_ascii=False, indent=2)
    return format_prompt(
        task_name="Stage 2 benchmark for shared post-input reasoning",
        instructions=instructions
        + """

You must use the category reference.
Choose the best matching reference entry when possible and copy its `reference_id`.
If the input only weakly matches a reference, still choose the closest reference and explain uncertainty in `risk_response`.
For food or household cleaner/spray style products, use ingredient-first reasoning.
For other categories, use material-first reasoning.
""",
        payload="This payload represents the normalized input that Stage 2 receives after either image OCR structuring or direct user text entry.\n\n"
        + payload,
        include_category_reference=True,
    )


def run_case(
    processor: AutoProcessor,
    model: AutoModelForCausalLM,
    case: Any,
    normalized_input: dict[str, str],
) -> tuple[str, dict[str, Any]]:
    prompt = build_stage2_prompt(case, normalized_input)
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    prompt_str = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    inputs = processor(text=prompt_str, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=260, do_sample=False)
    generated_ids = output[0][inputs.input_ids.shape[-1] :]
    response = processor.decode(generated_ids, skip_special_tokens=True)
    parsed = extract_json_object(response)
    return response, parsed


def category_score(pred: str, truth: str) -> float:
    return 1.0 if normalize_text(pred) == normalize_text(truth) else 0.0


def material_score(pred: str, truth: str) -> float:
    return 1.0 if normalize_text(pred) == normalize_text(truth) else 0.0


def info_priority_score(pred: str, truth: str) -> float:
    return 1.0 if normalize_text(pred) == normalize_text(truth) else 0.0


def call_openai_stage2_judge(
    *,
    api_key: str,
    model: str,
    case: Any,
    truth: dict[str, str],
    normalized_input: dict[str, str],
    candidate: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    judge_prompt = f"""
You are judging Stage 2 consumer-safety reasoning quality for a consumer safety app.

Evaluate the candidate answer on:
1. whether category identification is appropriate for downstream reasoning
2. whether the risk response is cautious, useful, and aligned with the expected regulatory nuance

Ground-truth category expectations:
{json.dumps(truth, ensure_ascii=False)}

Normalized Stage 2 input:
{json.dumps(normalized_input, ensure_ascii=False, indent=2)}

Expected benchmark labels:
{json.dumps(case.expected, ensure_ascii=False)}

Candidate JSON:
{json.dumps(candidate, ensure_ascii=False, indent=2)}

Return ONLY valid JSON with these keys:
- category_identification_score_5
- risk_response_score_5
- recommendation_alignment_score_5
- source_awareness_score_5
- short_reason

Scoring guidance:
- 5 means strong and appropriate
- 3 means mixed or only partially aligned
- 1 means mostly wrong or not useful
- 0 means unusable

Do not judge OCR. Judge only the Stage 2 text reasoning result.
""".strip()

    payload = {"model": model, "input": judge_prompt}
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
        parts = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    parts.append(content.get("text", ""))
        output_text = "\n".join(part for part in parts if part)
    parsed = extract_json_object(output_text)
    return output_text, parsed


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage 2 benchmark for direct text-input category identification and risk response.")
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--judge-model", default="gpt-4.1-mini")
    args = parser.parse_args()

    cases = load_cases(args.cases_path)
    if args.limit > 0:
        cases = cases[: args.limit]
    if not cases:
        raise RuntimeError("No Stage 2 cases selected.")

    api_key = load_openai_api_key()
    processor, model = load_model()

    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = DEFAULT_OUTPUT_ROOT / run_stamp
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, start=1):
        print(f"[{idx}/{len(cases)}] {case.case_id}", flush=True)
        truth = STAGE2_TRUTH[case.case_id]
        normalized_input = build_stage2_input(case)
        raw_text, parsed = run_case(processor, model, case, normalized_input)
        cat_score = category_score(parsed.get("product_use_category", ""), truth["product_use_category"])
        mat_score = material_score(parsed.get("material_or_form", ""), truth["material_or_form"])
        priority_score = info_priority_score(parsed.get("information_priority", ""), truth["information_priority"])
        judge_raw, judge = call_openai_stage2_judge(
            api_key=api_key,
            model=args.judge_model,
            case=case,
            truth=truth,
            normalized_input=normalized_input,
            candidate=parsed,
        )
        results.append(
            {
                "case_id": case.case_id,
                "product_name": case.product_name,
                "normalized_input": normalized_input,
                "truth": truth,
                "gemma_raw_output": raw_text,
                "gemma_parsed_output": parsed,
                "category_correct": cat_score,
                "material_correct": mat_score,
                "information_priority_correct": priority_score,
                "openai_judge_raw": judge_raw,
                "openai_judge": judge,
            }
        )

    mean_category = mean(item["category_correct"] for item in results)
    mean_material = mean(item["material_correct"] for item in results)
    mean_priority = mean(item["information_priority_correct"] for item in results)
    mean_risk = mean(safe_float(item["openai_judge"].get("risk_response_score_5")) for item in results)
    mean_category_judge = mean(safe_float(item["openai_judge"].get("category_identification_score_5")) for item in results)
    mean_reco = mean(safe_float(item["openai_judge"].get("recommendation_alignment_score_5")) for item in results)
    mean_source = mean(safe_float(item["openai_judge"].get("source_awareness_score_5")) for item in results)

    summary = {
        "stage": "stage2_text",
        "case_count": len(results),
        "mean_category_correct": round(mean_category, 4),
        "mean_material_correct": round(mean_material, 4),
        "mean_information_priority_correct": round(mean_priority, 4),
        "mean_openai_category_identification_score_5": round(mean_category_judge, 4),
        "mean_openai_risk_response_score_5": round(mean_risk, 4),
        "mean_openai_recommendation_alignment_score_5": round(mean_reco, 4),
        "mean_openai_source_awareness_score_5": round(mean_source, 4),
        "judge_model": args.judge_model,
    }

    (output_dir / "stage2_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "stage2_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Stage 2 Text Benchmark",
        "",
        f"- Cases: `{summary['case_count']}`",
        f"- Category exact accuracy: `{summary['mean_category_correct']:.3f}`",
        f"- Material/form exact accuracy: `{summary['mean_material_correct']:.3f}`",
        f"- Ingredient/material priority accuracy: `{summary['mean_information_priority_correct']:.3f}`",
        f"- OpenAI category identification score (0-5): `{summary['mean_openai_category_identification_score_5']:.3f}`",
        f"- OpenAI risk response score (0-5): `{summary['mean_openai_risk_response_score_5']:.3f}`",
        f"- OpenAI recommendation alignment score (0-5): `{summary['mean_openai_recommendation_alignment_score_5']:.3f}`",
        f"- OpenAI source awareness score (0-5): `{summary['mean_openai_source_awareness_score_5']:.3f}`",
        "",
        "## Per-case",
    ]
    for item in results:
        judge = item["openai_judge"]
        lines.append(
            f"- `{item['case_id']}`: category_exact `{item['category_correct']:.0f}`, "
            f"material_exact `{item['material_correct']:.0f}`, "
            f"priority_exact `{item['information_priority_correct']:.0f}`, "
            f"category_judge `{safe_float(judge.get('category_identification_score_5')):.1f}/5`, "
            f"risk `{safe_float(judge.get('risk_response_score_5')):.1f}/5`, "
            f"reco `{safe_float(judge.get('recommendation_alignment_score_5')):.1f}/5`, "
            f"source `{safe_float(judge.get('source_awareness_score_5')):.1f}/5`"
        )
    (output_dir / "stage2_report.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"Output directory: {output_dir}", flush=True)
    print(f"Category exact accuracy: {summary['mean_category_correct']:.3f}", flush=True)
    print(f"Risk response score: {summary['mean_openai_risk_response_score_5']:.3f}/5", flush=True)


if __name__ == "__main__":
    main()
