import argparse
import csv
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import kagglehub
import torch
from transformers import AutoModelForCausalLM, AutoProcessor


VARIATION = "gemma-4-e4b-it"
MODEL_HANDLE = f"google/gemma-4/transformers/{VARIATION}"
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CASES_PATH = PROJECT_ROOT / "benchmark_cases.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "pretest"
DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "data" / "app_data" / "regulatory_evidence.csv"
DEFAULT_PROP65_PATH = PROJECT_ROOT / "data" / "data" / "prop65_full.csv"
DEFAULT_WHO_PATH = PROJECT_ROOT / "data" / "data" / "who_iarc_cancer_risk_list.csv"
DEFAULT_EU_FOOD_PATH = PROJECT_ROOT / "data" / "data" / "eu_food_additives.csv"
DEFAULT_CANADA_FOOD_PATH = PROJECT_ROOT / "data" / "data" / "health_canada_food_additives.csv"
DEFAULT_FDA_FOOD_CONTACT_PATH = PROJECT_ROOT / "data" / "data" / "fda_food_contact_indirect_additives.csv"

JSON_KEYS = [
    "product_summary",
    "ingredient_or_signal",
    "prop65_assessment",
    "who_assessment",
    "allowed_or_authorized_signal",
    "ban_or_restriction_signal",
    "threshold_or_limit_signal",
    "guidance_bucket",
    "occasional_use_view",
    "reasoning_short",
    "source_types_to_check",
]

NORMALIZED_VALUES = {
    "yes": {"yes", "likely yes", "probably yes", "present", "listed", "true"},
    "no": {"no", "likely no", "probably no", "not listed", "absent", "false"},
    "unknown": {"unknown", "unclear", "insufficient info", "not sure", "cannot tell"},
}


@dataclass
class BenchmarkCase:
    case_id: str
    product_name: str
    region: str
    observed_signal: str
    user_question: str
    expected: dict[str, Any]


def load_kaggle_credentials() -> bool:
    kaggle_dir = Path.home() / ".kaggle"
    user_file = kaggle_dir / "user_name"
    token_file = kaggle_dir / "access_token"
    if not user_file.exists() or not token_file.exists():
        return False
    os.environ["KAGGLE_USERNAME"] = user_file.read_text().strip()
    os.environ["KAGGLE_KEY"] = token_file.read_text().strip()
    return True


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def normalize_categorical(value: Any) -> str:
    text = normalize_text(str(value))
    for canonical, variants in NORMALIZED_VALUES.items():
        if text in variants:
            return canonical
    return text or "unknown"


def load_cases(path: Path) -> list[BenchmarkCase]:
    raw_cases = json.loads(path.read_text())
    return [
        BenchmarkCase(
            case_id=item["id"],
            product_name=item["product_name"],
            region=item["region"],
            observed_signal=item["observed_signal"],
            user_question=item["user_question"],
            expected=item["expected"],
        )
        for item in raw_cases
    ]


def load_model() -> tuple[AutoProcessor, AutoModelForCausalLM]:
    if not load_kaggle_credentials():
        raise RuntimeError("Kaggle credentials not found under ~/.kaggle.")

    model_path = kagglehub.model_download(MODEL_HANDLE)
    processor = AutoProcessor.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    return processor, model


def build_prompt(case: BenchmarkCase) -> str:
    return f"""
You are being evaluated on consumer product safety reasoning without using any external tools, databases, or retrieval.

Return ONLY valid JSON with exactly these keys:
{json.dumps(JSON_KEYS)}

Allowed values:
- prop65_assessment: yes / no / unknown
- who_assessment: yes / no / unknown
- allowed_or_authorized_signal: yes / no / unknown
- ban_or_restriction_signal: yes / no / unknown
- threshold_or_limit_signal: yes / no / unknown
- guidance_bucket: higher_concern / context_dependent / likely_lower_concern / insufficient_info
- occasional_use_view: avoid / limit / likely_okay / insufficient_info
- source_types_to_check: array of at most 3 short strings

Rules:
- Be cautious.
- A hazard listing is not the same as proof that the product is unsafe.
- A warning list is not the same as a ban.
- "Allowed with conditions" should not be treated the same as "harmless".
- If the signal looks process-formed or context-dependent, say so briefly.
- Keep product_summary under 6 words.
- Keep reasoning_short under 12 words.
- Keep source_types_to_check to at most 3 items.

Case:
- Product: {case.product_name}
- Region: {case.region}
- Observed ingredient or signal: {case.observed_signal}
- User question: {case.user_question}
""".strip()


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*)", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        start = text.find("{")
        if start != -1:
            text = text[start:]

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    recovered: dict[str, Any] = {}
    for key in JSON_KEYS:
        string_match = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"\n]*)"', text)
        if string_match:
            recovered[key] = string_match.group(1)
            continue
        array_match = re.search(rf'"{re.escape(key)}"\s*:\s*\[(.*?)\]', text, flags=re.DOTALL)
        if array_match:
            recovered[key] = re.findall(r'"([^"\n]+)"', array_match.group(1))
            continue

    return recovered


def run_case(processor: AutoProcessor, model: AutoModelForCausalLM, case: BenchmarkCase) -> tuple[str, dict[str, Any]]:
    prompt = build_prompt(case)
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    prompt_str = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    inputs = processor(text=prompt_str, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=150,
            do_sample=False,
        )

    generated_ids = output[0][inputs.input_ids.shape[-1] :]
    response = processor.decode(generated_ids, skip_special_tokens=True)
    parsed = extract_json_object(response)
    return response, parsed


def strict_score(pred: str, truth: str) -> float:
    return 1.0 if pred == truth else 0.0


def lenient_score(pred: str, truth: str) -> float:
    if pred == truth:
        return 1.0
    if pred == "unknown":
        return 0.5
    return 0.0


def score_case(case: BenchmarkCase, parsed: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "prop65_assessment",
        "who_assessment",
        "allowed_or_authorized_signal",
        "ban_or_restriction_signal",
        "threshold_or_limit_signal",
        "guidance_bucket",
        "occasional_use_view",
    ]
    scores: dict[str, Any] = {}
    strict_total = 0.0
    lenient_total = 0.0

    for field in fields:
        truth = normalize_categorical(case.expected[field])
        pred = normalize_categorical(parsed.get(field, "unknown"))
        scores[f"{field}_truth"] = truth
        scores[f"{field}_pred"] = pred
        scores[f"{field}_strict"] = strict_score(pred, truth)
        scores[f"{field}_lenient"] = lenient_score(pred, truth)
        strict_total += scores[f"{field}_strict"]
        lenient_total += scores[f"{field}_lenient"]

    expected_sources = [normalize_text(x) for x in case.expected.get("expected_source_types", [])]
    predicted_sources = [normalize_text(x) for x in parsed.get("source_types_to_check", []) if isinstance(x, str)]

    matched_sources = 0
    for expected_source in expected_sources:
        if any(expected_source in pred or pred in expected_source for pred in predicted_sources):
            matched_sources += 1

    source_recall = matched_sources / len(expected_sources) if expected_sources else 1.0
    false_reassurance = (
        scores["prop65_assessment_truth"] == "yes"
        and scores["prop65_assessment_pred"] == "no"
    ) or (
        scores["ban_or_restriction_signal_truth"] == "yes"
        and scores["guidance_bucket_pred"] == "likely_lower_concern"
    )

    scores["source_recall"] = round(source_recall, 4)
    scores["false_reassurance_flag"] = bool(false_reassurance)
    scores["strict_average"] = round(strict_total / len(fields), 4)
    scores["lenient_average"] = round(lenient_total / len(fields), 4)
    return scores


def load_truth_evidence() -> dict[str, list[dict[str, str]]]:
    files = {
        "prop65": DEFAULT_PROP65_PATH,
        "who": DEFAULT_WHO_PATH,
        "eu_food": DEFAULT_EU_FOOD_PATH,
        "canada_food": DEFAULT_CANADA_FOOD_PATH,
        "fda_food_contact": DEFAULT_FDA_FOOD_CONTACT_PATH,
        "regulatory_evidence": DEFAULT_EVIDENCE_PATH,
    }
    loaded: dict[str, list[dict[str, str]]] = {}
    for key, path in files.items():
        with path.open(newline="", encoding="utf-8-sig") as f:
            loaded[key] = list(csv.DictReader(f))
    return loaded


def collect_supporting_evidence(case: BenchmarkCase, evidence_tables: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    signal = case.observed_signal.split(":", 1)[-1].strip()
    signal_lower = signal.lower()
    matches: list[dict[str, str]] = []
    for source_name, rows in evidence_tables.items():
        for row in rows:
            substance = row.get("substance_name") or row.get("preferred_name") or ""
            if substance.lower() == signal_lower or substance.lower() in signal_lower or signal_lower in substance.lower():
                match = {
                    "source_table": source_name,
                    "substance_name": substance,
                    "jurisdiction": row.get("country_or_jurisdiction", ""),
                    "product_scope": row.get("product_scope", ""),
                    "regulatory_status": row.get("regulatory_status", ""),
                    "hazard_basis": row.get("hazard_basis", ""),
                    "threshold_value": row.get("threshold_value", ""),
                    "threshold_unit": row.get("threshold_unit", ""),
                    "citation_url": row.get("citation_url", ""),
                }
                matches.append(match)
    return matches[:12]


def write_outputs(
    output_dir: Path,
    cases: list[BenchmarkCase],
    raw_outputs: dict[str, str],
    parsed_outputs: dict[str, dict[str, Any]],
    scores: dict[str, dict[str, Any]],
    evidence_tables: dict[str, list[dict[str, str]]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / "raw_model_outputs.json").open("w", encoding="utf-8") as f:
        json.dump(raw_outputs, f, ensure_ascii=False, indent=2)

    with (output_dir / "parsed_predictions.json").open("w", encoding="utf-8") as f:
        json.dump(parsed_outputs, f, ensure_ascii=False, indent=2)

    with (output_dir / "case_scores.json").open("w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)

    csv_fields = [
        "case_id",
        "product_name",
        "observed_signal",
        "prop65_assessment_truth",
        "prop65_assessment_pred",
        "who_assessment_truth",
        "who_assessment_pred",
        "allowed_or_authorized_signal_truth",
        "allowed_or_authorized_signal_pred",
        "ban_or_restriction_signal_truth",
        "ban_or_restriction_signal_pred",
        "threshold_or_limit_signal_truth",
        "threshold_or_limit_signal_pred",
        "guidance_bucket_truth",
        "guidance_bucket_pred",
        "occasional_use_view_truth",
        "occasional_use_view_pred",
        "source_recall",
        "false_reassurance_flag",
        "strict_average",
        "lenient_average",
    ]
    with (output_dir / "case_scores.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for case in cases:
            row = {
                "case_id": case.case_id,
                "product_name": case.product_name,
                "observed_signal": case.observed_signal,
            }
            row.update(scores[case.case_id])
            writer.writerow({key: row.get(key, "") for key in csv_fields})

    report_lines = []
    report_lines.append("# Gemma 4 No-Retrieval Pre-Test")
    report_lines.append("")
    report_lines.append(f"- Run date: {datetime.now().isoformat(timespec='seconds')}")
    report_lines.append(f"- Model: `{VARIATION}`")
    report_lines.append(f"- Cases: `{len(cases)}`")
    report_lines.append("- Evaluation mode: no database retrieval, model-only reasoning")
    report_lines.append("")

    strict_scores = [scores[case.case_id]["strict_average"] for case in cases]
    lenient_scores = [scores[case.case_id]["lenient_average"] for case in cases]
    false_reassurance_count = sum(1 for case in cases if scores[case.case_id]["false_reassurance_flag"])

    report_lines.append("## Summary")
    report_lines.append("")
    report_lines.append(f"- Mean strict score: `{sum(strict_scores) / len(strict_scores):.3f}`")
    report_lines.append(f"- Mean lenient score: `{sum(lenient_scores) / len(lenient_scores):.3f}`")
    report_lines.append(f"- False reassurance flags: `{false_reassurance_count}`")
    report_lines.append("")

    bucket_counter = Counter()
    for case in cases:
        bucket_counter[scores[case.case_id]["guidance_bucket_pred"]] += 1
    report_lines.append("## Predicted Guidance Distribution")
    report_lines.append("")
    for bucket, count in bucket_counter.most_common():
        report_lines.append(f"- `{bucket}`: `{count}`")
    report_lines.append("")

    report_lines.append("## Case Review")
    report_lines.append("")
    for case in cases:
        parsed = parsed_outputs[case.case_id]
        score = scores[case.case_id]
        evidence_rows = collect_supporting_evidence(case, evidence_tables)
        report_lines.append(f"### {case.case_id}")
        report_lines.append("")
        report_lines.append(f"- Product: `{case.product_name}`")
        report_lines.append(f"- Signal: `{case.observed_signal}`")
        report_lines.append(f"- Strict / lenient: `{score['strict_average']}` / `{score['lenient_average']}`")
        report_lines.append(f"- False reassurance: `{score['false_reassurance_flag']}`")
        report_lines.append(f"- Model guidance: `{parsed.get('guidance_bucket', 'missing')}`")
        report_lines.append(f"- Model reasoning: {parsed.get('reasoning_short', '')}")
        report_lines.append(f"- Expected source types: `{', '.join(case.expected.get('expected_source_types', []))}`")
        report_lines.append(f"- Model source types: `{', '.join(parsed.get('source_types_to_check', []))}`")
        report_lines.append("")
        if evidence_rows:
            report_lines.append("Supporting evidence snapshots:")
            for row in evidence_rows[:5]:
                threshold = " ".join([row.get("threshold_value", "").strip(), row.get("threshold_unit", "").strip()]).strip()
                report_lines.append(
                    f"- `{row['source_table']}` | `{row['jurisdiction']}` | `{row['regulatory_status']}` | `{row['hazard_basis']}` | `{threshold}`"
                )
            report_lines.append("")

    report_lines.append("## Notes")
    report_lines.append("")
    report_lines.append("- This pre-test measures model reasoning without retrieval.")
    report_lines.append("- The benchmark is strongest for regulatory-signal detection, not nutrition coaching.")
    report_lines.append("- If the model overstates danger for allowed additives or misses threshold nuance, that is exactly the gap the retrieval layer should fix.")
    report_lines.append("")

    (output_dir / "pretest_report.md").write_text("\n".join(report_lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a no-retrieval Gemma 4 pre-test against fixed consumer safety benchmark cases.")
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0, help="Run only the first N cases. 0 means all cases.")
    parser.add_argument("--case-id", action="append", default=[], help="Run only the specified case id. Can be passed multiple times.")
    args = parser.parse_args()

    cases = load_cases(args.cases_path)
    if args.case_id:
        wanted = set(args.case_id)
        cases = [case for case in cases if case.case_id in wanted]
    if args.limit > 0:
        cases = cases[: args.limit]

    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or (DEFAULT_OUTPUT_ROOT / run_stamp)

    print(f"Loading model {VARIATION}...", flush=True)
    processor, model = load_model()

    raw_outputs: dict[str, str] = {}
    parsed_outputs: dict[str, dict[str, Any]] = {}
    scores: dict[str, dict[str, Any]] = {}
    evidence_tables = load_truth_evidence()
    output_dir.mkdir(parents=True, exist_ok=True)

    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] Running case: {case.case_id}", flush=True)
        raw_text, parsed = run_case(processor, model, case)
        raw_outputs[case.case_id] = raw_text
        parsed_outputs[case.case_id] = parsed
        scores[case.case_id] = score_case(case, parsed)
        write_outputs(output_dir, cases[:index], raw_outputs, parsed_outputs, scores, evidence_tables)
        print(
            f"  strict={scores[case.case_id]['strict_average']:.3f} "
            f"lenient={scores[case.case_id]['lenient_average']:.3f} "
            f"false_reassurance={scores[case.case_id]['false_reassurance_flag']}",
            flush=True,
        )

    write_outputs(output_dir, cases, raw_outputs, parsed_outputs, scores, evidence_tables)

    strict_mean = sum(scores[c.case_id]["strict_average"] for c in cases) / len(cases)
    lenient_mean = sum(scores[c.case_id]["lenient_average"] for c in cases) / len(cases)
    false_reassurance_count = sum(1 for c in cases if scores[c.case_id]["false_reassurance_flag"])
    print("", flush=True)
    print(f"Output directory: {output_dir}", flush=True)
    print(f"Mean strict score: {strict_mean:.3f}", flush=True)
    print(f"Mean lenient score: {lenient_mean:.3f}", flush=True)
    print(f"False reassurance flags: {false_reassurance_count}", flush=True)


if __name__ == "__main__":
    main()
