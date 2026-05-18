import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from run_gemma4_pretest import (
    DEFAULT_CASES_PATH,
    DEFAULT_OUTPUT_ROOT,
    BenchmarkCase,
    build_prompt,
    extract_json_object,
    load_cases,
    load_truth_evidence,
    score_case,
    write_outputs,
)


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_KEY_PATH = Path.home() / ".ssh" / "openai_api_key.txt"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def load_openai_api_key(path: Path = DEFAULT_KEY_PATH) -> str:
    key = path.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError(f"OpenAI API key file is empty: {path}")
    return key


def call_openai_responses_api(
    api_key: str,
    model: str,
    case: BenchmarkCase,
    temperature: float | None = None,
) -> tuple[str, dict[str, Any]]:
    payload = {
        "model": model,
        "input": build_prompt(case),
    }
    if temperature is not None:
        payload["temperature"] = temperature
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
        with urllib.request.urlopen(request, timeout=180) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {error_body}") from exc

    data = json.loads(body)
    output_text = data.get("output_text", "")
    if not output_text:
        output_parts = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    output_parts.append(content.get("text", ""))
        output_text = "\n".join(part for part in output_parts if part)
    parsed = extract_json_object(output_text)
    return output_text, parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the fixed consumer-safety benchmark against the OpenAI API.")
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--model", default="gpt-5")
    parser.add_argument("--temperature", type=float, default=0.0)
    args = parser.parse_args()

    cases = load_cases(args.cases_path)
    if args.case_id:
        wanted = set(args.case_id)
        cases = [case for case in cases if case.case_id in wanted]
    if args.limit > 0:
        cases = cases[: args.limit]
    if not cases:
        raise RuntimeError("No benchmark cases selected.")

    api_key = load_openai_api_key()
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or (DEFAULT_OUTPUT_ROOT / f"openai_{run_stamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_outputs: dict[str, str] = {}
    parsed_outputs: dict[str, dict[str, Any]] = {}
    scores: dict[str, dict[str, Any]] = {}
    evidence_tables = load_truth_evidence()

    print(f"Running OpenAI benchmark with model={args.model} on {len(cases)} cases...", flush=True)
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case.case_id}", flush=True)
        raw_text, parsed = call_openai_responses_api(
            api_key=api_key,
            model=args.model,
            case=case,
            temperature=args.temperature if args.temperature > 0 else None,
        )
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

    summary = {
        "provider": "openai",
        "model": args.model,
        "case_count": len(cases),
        "mean_strict_score": round(strict_mean, 4),
        "mean_lenient_score": round(lenient_mean, 4),
        "false_reassurance_flags": false_reassurance_count,
        "output_dir": str(output_dir),
    }
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("", flush=True)
    print(f"Output directory: {output_dir}", flush=True)
    print(f"Mean strict score: {strict_mean:.3f}", flush=True)
    print(f"Mean lenient score: {lenient_mean:.3f}", flush=True)
    print(f"False reassurance flags: {false_reassurance_count}", flush=True)


if __name__ == "__main__":
    main()
