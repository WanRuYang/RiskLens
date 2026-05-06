import argparse
import json
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

import requests
import torch
from transformers import AutoModelForCausalLM, AutoProcessor

from prompt_utils import format_prompt
from run_gemma4_pretest import load_cases, load_model
from run_openai_pretest import load_openai_api_key
from run_stage2_text_benchmark import (
    DEFAULT_CASES_PATH,
    STAGE2_TRUTH,
    build_stage2_input,
    category_score,
    extract_json_object,
    info_priority_score,
    material_score,
    safe_float,
)


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "stage2_grounded_benchmark"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
API_BASE_URL = os.getenv("GEMMA4GOOD_API_BASE_URL", "http://127.0.0.1:8010")


def call_local_api(normalized_input: dict[str, str]) -> dict[str, Any]:
    payload = {
        "user_id": "stage2_grounded_benchmark",
        "session_id": str(uuid.uuid4()),
        "product_name": normalized_input.get("product_name", ""),
        "raw_ocr_text": "",
        "ingredients_text": " | ".join(
            part
            for part in [
                normalized_input.get("ingredient_text", ""),
                normalized_input.get("category_clues", ""),
            ]
            if part
        ),
        "warning_text": normalized_input.get("warning_text", ""),
        "region": normalized_input.get("region", "") or "California, USA",
        "save_to_history": False,
    }
    response = requests.post(f"{API_BASE_URL}/analyze-product", json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


def compact_grounding(api_result: dict[str, Any]) -> dict[str, Any]:
    serving = api_result.get("serving_recommendation") or {}
    return {
        "inferred_category": api_result.get("inferred_category", {}),
        "evidence_scope_summary": api_result.get("evidence_scope_summary", {}),
        "chemical_matches": [
            {
                "preferred_name": row.get("preferred_name"),
                "matched_term": row.get("matched_term"),
            }
            for row in api_result.get("chemical_matches", [])[:5]
        ],
        "concern_sources": api_result.get("concern_sources", [])[:4],
        "serving_recommendation": {
            key: serving.get(key)
            for key in [
                "product_use_category",
                "material_subcategory",
                "top_chemical_families",
                "top_chemicals",
                "recommendation_priority",
                "recommended_caution_text",
                "why_this_matters",
            ]
        },
        "recommendation": api_result.get("recommendation", {}),
        "user_overlap_summary": api_result.get("user_overlap_summary", []),
    }


def build_grounded_prompt(case: Any, normalized_input: dict[str, str], grounding: dict[str, Any]) -> str:
    instructions = """
Return ONLY valid JSON with these keys:
- product_use_category
- material_or_form
- information_priority
- guidance_bucket
- occasional_use_view
- source_types_to_check
- missing_information_to_request
- risk_response

Rules:
- Use ONLY the normalized input and grounded API result below.
- Do not invent chemicals, legal status, or regions that are not supported by the grounding.
- product_use_category should be a short label such as food, food_contact, household, children_products, personal_care, bags_accessories, electronics, or unknown.
- material_or_form should be a short label.
- information_priority must be exactly one of:
  - ingredient_first
  - material_first
- If this is food, drink, supplement, or a household cleaner/spray, ingredient_first is usually the correct choice.
- Otherwise material_first is usually the correct choice.
- guidance_bucket should be one of:
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
- risk_response should be 2 to 4 sentences, cautious, and grounded in the API result.
- If the grounding mostly shows handling caution rather than a direct listed ingredient match, say that clearly.
- If the grounding shows category-level evidence only and no direct chemical match, do not present that as a direct problem with the provided ingredient.
- If the grounding shows category-level evidence only for a food ingredient case, guidance should usually stay at limited_signal_found or likely_lower_concern unless the input itself includes a warning or a direct listed chemical.
- In food additive cases without a direct match, source_types_to_check should prefer FDA authorization/product-use context or regional food additive rules before broad Prop 65 category signals.
- If the product is food_contact, information_priority should stay material_first even when a chemical clue is provided.
- If the product is a child-use product and the grounding shows a direct chemical match, guidance should usually lean higher_concern and occasional_use_view avoid.
- In child-use direct-match cases, source_types_to_check should usually include WHO or IARC hazard classification and regional children's product or toy restrictions.
"""
    payload = "\n\n".join(
        [
            "Normalized Stage 2 input:",
            json.dumps(normalized_input, ensure_ascii=False, indent=2),
            "Grounded API result:",
            json.dumps(grounding, ensure_ascii=False, indent=2),
            f"Original user question: {case.user_question}",
        ]
    )
    return format_prompt(
        task_name="Stage 2 grounded benchmark",
        instructions=instructions,
        payload=payload,
        include_category_reference=True,
    )


def run_gemma_case(
    processor: AutoProcessor,
    model: AutoModelForCausalLM,
    prompt: str,
) -> tuple[str, dict[str, Any]]:
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    prompt_str = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    inputs = processor(text=prompt_str, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=320, do_sample=False)
    generated_ids = output[0][inputs.input_ids.shape[-1] :]
    response = processor.decode(generated_ids, skip_special_tokens=True)
    return response, extract_json_object(response)


def run_openai_case(
    api_key: str,
    model: str,
    prompt: str,
) -> tuple[str, dict[str, Any]]:
    payload = {
        "model": model,
        "input": prompt,
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
        parts = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    parts.append(content.get("text", ""))
        output_text = "\n".join(part for part in parts if part)
    return output_text, extract_json_object(output_text)


def call_openai_judge(
    *,
    api_key: str,
    model: str,
    case: Any,
    truth: dict[str, str],
    normalized_input: dict[str, str],
    grounding: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    judge_prompt = f"""
You are judging grounded Stage 2 consumer-safety reasoning quality for a consumer safety app.

Ground-truth category expectations:
{json.dumps(truth, ensure_ascii=False)}

Normalized Stage 2 input:
{json.dumps(normalized_input, ensure_ascii=False, indent=2)}

Grounded API result:
{json.dumps(grounding, ensure_ascii=False, indent=2)}

Expected benchmark labels:
{json.dumps(case.expected, ensure_ascii=False)}

Candidate JSON:
{json.dumps(candidate, ensure_ascii=False, indent=2)}

Return ONLY valid JSON with these keys:
- category_identification_score_5
- grounding_fidelity_score_5
- risk_response_score_5
- recommendation_alignment_score_5
- source_awareness_score_5
- short_reason

Scoring guidance:
- 5 means strong and appropriately grounded
- 3 means mixed or partially aligned
- 1 means mostly wrong or not useful
- 0 means unusable

Judge whether the candidate uses the grounding correctly, not whether the underlying API is perfect.
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
    return output_text, extract_json_object(output_text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage 2 grounded benchmark using the local API and either Gemma or OpenAI.")
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--provider", choices=["gemma", "openai"], default="gemma")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--judge-model", default="gpt-4.1-mini")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    cases = load_cases(args.cases_path)
    if args.limit > 0:
        cases = cases[: args.limit]
    if not cases:
        raise RuntimeError("No grounded Stage 2 cases selected.")

    judge_api_key = load_openai_api_key()
    provider_api_key = judge_api_key if args.provider == "openai" else None
    processor: AutoProcessor | None = None
    model: AutoModelForCausalLM | None = None
    if args.provider == "gemma":
        processor, model = load_model()

    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = DEFAULT_OUTPUT_ROOT / f"{args.provider}_{run_stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, start=1):
        print(f"[{idx}/{len(cases)}] {case.case_id}", flush=True)
        truth = STAGE2_TRUTH[case.case_id]
        normalized_input = build_stage2_input(case)
        api_result = call_local_api(normalized_input)
        grounding = compact_grounding(api_result)
        prompt = build_grounded_prompt(case, normalized_input, grounding)
        if args.provider == "gemma":
            assert processor is not None and model is not None
            raw_text, parsed = run_gemma_case(processor, model, prompt)
        else:
            assert provider_api_key is not None
            raw_text, parsed = run_openai_case(provider_api_key, args.model, prompt)

        cat_score = category_score(parsed.get("product_use_category", ""), truth["product_use_category"])
        mat_score = material_score(parsed.get("material_or_form", ""), truth["material_or_form"])
        priority_score = info_priority_score(parsed.get("information_priority", ""), truth["information_priority"])
        judge_raw, judge = call_openai_judge(
            api_key=judge_api_key,
            model=args.judge_model,
            case=case,
            truth=truth,
            normalized_input=normalized_input,
            grounding=grounding,
            candidate=parsed,
        )
        results.append(
            {
                "case_id": case.case_id,
                "product_name": case.product_name,
                "normalized_input": normalized_input,
                "truth": truth,
                "grounding": grounding,
                "provider_raw_output": raw_text,
                "provider_parsed_output": parsed,
                "category_correct": cat_score,
                "material_correct": mat_score,
                "information_priority_correct": priority_score,
                "openai_judge_raw": judge_raw,
                "openai_judge": judge,
            }
        )

    summary = {
        "stage": "stage2_grounded",
        "provider": args.provider,
        "provider_model": args.model if args.provider == "openai" else "gemma-4-e4b-it",
        "case_count": len(results),
        "mean_category_correct": round(mean(item["category_correct"] for item in results), 4),
        "mean_material_correct": round(mean(item["material_correct"] for item in results), 4),
        "mean_information_priority_correct": round(mean(item["information_priority_correct"] for item in results), 4),
        "mean_openai_category_identification_score_5": round(
            mean(safe_float(item["openai_judge"].get("category_identification_score_5")) for item in results), 4
        ),
        "mean_openai_grounding_fidelity_score_5": round(
            mean(safe_float(item["openai_judge"].get("grounding_fidelity_score_5")) for item in results), 4
        ),
        "mean_openai_risk_response_score_5": round(
            mean(safe_float(item["openai_judge"].get("risk_response_score_5")) for item in results), 4
        ),
        "mean_openai_recommendation_alignment_score_5": round(
            mean(safe_float(item["openai_judge"].get("recommendation_alignment_score_5")) for item in results), 4
        ),
        "mean_openai_source_awareness_score_5": round(
            mean(safe_float(item["openai_judge"].get("source_awareness_score_5")) for item in results), 4
        ),
        "judge_model": args.judge_model,
    }

    (output_dir / "stage2_grounded_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "stage2_grounded_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        f"# Stage 2 Grounded Benchmark ({args.provider})",
        "",
        f"- Cases: `{summary['case_count']}`",
        f"- Category exact accuracy: `{summary['mean_category_correct']:.3f}`",
        f"- Material/form exact accuracy: `{summary['mean_material_correct']:.3f}`",
        f"- Ingredient/material priority accuracy: `{summary['mean_information_priority_correct']:.3f}`",
        f"- OpenAI category identification score (0-5): `{summary['mean_openai_category_identification_score_5']:.3f}`",
        f"- OpenAI grounding fidelity score (0-5): `{summary['mean_openai_grounding_fidelity_score_5']:.3f}`",
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
            f"grounding `{safe_float(judge.get('grounding_fidelity_score_5')):.1f}/5`, "
            f"risk `{safe_float(judge.get('risk_response_score_5')):.1f}/5`, "
            f"reco `{safe_float(judge.get('recommendation_alignment_score_5')):.1f}/5`, "
            f"source `{safe_float(judge.get('source_awareness_score_5')):.1f}/5`"
        )
    (output_dir / "stage2_grounded_report.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"Output directory: {output_dir}", flush=True)
    print(f"Category exact accuracy: {summary['mean_category_correct']:.3f}", flush=True)
    print(f"Grounding fidelity score: {summary['mean_openai_grounding_fidelity_score_5']:.3f}/5", flush=True)
    print(f"Risk response score: {summary['mean_openai_risk_response_score_5']:.3f}/5", flush=True)


if __name__ == "__main__":
    main()
