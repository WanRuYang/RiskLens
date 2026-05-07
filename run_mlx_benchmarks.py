import argparse
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from PIL import Image
import mlx_vlm

from prompt_utils import extract_json_object, format_prompt
from mlx_engine import (
    get_model, 
    ocr_prompt, 
    structure_prompt, 
    final_answer_prompt, 
    call_local_api,
    run_mlx_ocr_multi,
    run_mlx_generation,
    verify_category_vlm,
    run_tiled_ocr,
    run_hybrid_ocr
)

PROJECT_ROOT = Path(__file__).resolve().parent
OCR_CASES_PATH = PROJECT_ROOT / "benchmark_ocr_cases.json"
GROUNDED_CASES_PATH = PROJECT_ROOT / "benchmark_cases.json"
OCR_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "ocr_benchmark"
GROUNDED_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "stage2_grounded_benchmark"

# For scoring grounded
try:
    from run_stage2_text_benchmark import (
        STAGE2_TRUTH,
        category_score,
        info_priority_score,
        material_score,
        safe_float,
    )
except ImportError:
    STAGE2_TRUTH = {}
    def category_score(*args): return 0
    def info_priority_score(*args): return 0
    def material_score(*args): return 0
    def safe_float(v): return float(v) if v else 0.0

import re

def normalize_text(text: str) -> str:
    """
    Normalizes text for robust substring matching by removing punctuation and extra whitespace.
    """
    if not text: return ""
    # Remove all punctuation
    text = re.sub(r'[^\w\s]', '', text)
    # Lowercase and collapse whitespace
    return " ".join(text.lower().split())

def score_ocr_case(extracted_text: str, expected_strings: list[str]) -> dict[str, Any]:
    # v3.2: Soft matching to handle punctuation noise in benchmark data
    normalized_extracted = normalize_text(extracted_text)
    
    results = []
    hit_count = 0
    for item in expected_strings:
        normalized_expected = normalize_text(item)
        if not normalized_expected:
            hit = True
        else:
            hit = normalized_expected in normalized_extracted
            
        results.append({"expected": item, "hit": hit})
        hit_count += int(hit)
    
    recall = hit_count / len(expected_strings) if expected_strings else 1.0
    return {
        "expected_count": len(expected_strings),
        "hit_count": hit_count,
        "substring_recall": round(recall, 4),
        "matches": results,
    }

def run_ocr_benchmarks(limit: int = 0, tiled: bool = False, hybrid: bool = False):
    print(f"Starting MLX OCR Benchmarks (Tiled: {tiled}, Hybrid: {hybrid})...")
    cases = json.loads(OCR_CASES_PATH.read_text())
    if limit > 0:
        cases = cases[:limit]
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if hybrid:
        suffix = "_hybrid_mlx"
    elif tiled:
        suffix = "_tiled_mlx"
    else:
        suffix = "_mlx"
        
    output_dir = OCR_OUTPUT_ROOT / f"{timestamp}{suffix}"
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs = {}
    summary_rows = []
    
    start_time = time.time()
    for idx, case in enumerate(cases, start=1):
        case_id = case["id"]
        image_paths = case.get("image_paths", [case.get("image_path")])
        expected_strings = case.get("expected_strings", [])
        
        print(f"[{idx}/{len(cases)}] Case: {case_id}")
        
        # Run OCR
        case_start = time.time()
        if hybrid:
            chunks = []
            for path in image_paths:
                if path:
                    extracted = run_hybrid_ocr(path)
                    chunks.append(extracted)
            extracted_text = "\n\n".join(chunks)
        elif tiled:
            chunks = []
            for path in image_paths:
                if path:
                    extracted = run_tiled_ocr(path)
                    chunks.append(extracted)
            extracted_text = "\n\n".join(chunks)
        else:
            extracted_text = run_mlx_ocr_multi(image_paths)
        
        case_duration = time.time() - case_start
        
        score = score_ocr_case(extracted_text, expected_strings)
        outputs[case_id] = {
            "image_paths": image_paths,
            "expected_strings": expected_strings,
            "extracted_text": extracted_text,
            "score": score,
            "duration_sec": round(case_duration, 2)
        }
        summary_rows.append({
            "case_id": case_id,
            "substring_recall": score["substring_recall"],
            "expected_count": score["expected_count"],
            "hit_count": score["hit_count"],
            "duration_sec": round(case_duration, 2)
        })

    total_duration = time.time() - start_time
    mean_recall = mean(row["substring_recall"] for row in summary_rows)
    
    (output_dir / "ocr_outputs_mlx.json").write_text(json.dumps(outputs, indent=2, ensure_ascii=False))
    (output_dir / "ocr_summary_mlx.json").write_text(json.dumps(summary_rows, indent=2, ensure_ascii=False))
    
    report = [
        f"# Gemma 4 MLX OCR Benchmark",
        f"- Date: {timestamp}",
        f"- Cases: {len(summary_rows)}",
        f"- Mean Recall: {mean_recall:.3f}",
        f"- Total Duration: {total_duration:.2f}s",
        f"- Avg Duration per Case: {total_duration/len(summary_rows):.2f}s",
        "",
        "## Per-case",
    ]
    for row in summary_rows:
        report.append(f"- `{row['case_id']}`: recall `{row['substring_recall']:.3f}` ({row['hit_count']}/{row['expected_count']})")
    
    (output_dir / "ocr_report_mlx.md").write_text("\n".join(report))
    print(f"OCR Benchmarks complete. Output: {output_dir}")

def run_grounded_benchmarks(limit: int = 0):
    print("Starting MLX Grounded Benchmarks...")
    # benchmark_cases.json contains a list of cases, each might have multiple fields
    # We need to adapt to run_stage2_grounded_benchmark logic
    try:
        from run_gemma4_pretest import load_cases as load_grounded_cases
        cases = load_grounded_cases(GROUNDED_CASES_PATH)
    except:
        cases = json.loads(GROUNDED_CASES_PATH.read_text())
        
    if limit > 0:
        cases = cases[:limit]
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = GROUNDED_OUTPUT_ROOT / f"mlx_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    start_time = time.time()
    
    for idx, case in enumerate(cases, start=1):
        case_id = getattr(case, 'case_id', str(idx))
        print(f"[{idx}/{len(cases)}] Case: {case_id}")
        
        # Build Stage 2 Input
        try:
            from run_stage2_text_benchmark import build_stage2_input
            normalized_input = build_stage2_input(case)
        except:
            normalized_input = {
                "product_name": getattr(case, 'product_name', ''),
                "ingredient_text": getattr(case, 'ingredients', ''),
                "warning_text": getattr(case, 'warning_text', ''),
                "region": "California, USA"
            }

        # Stage 2 Grounded Pipeline
        case_start = time.time()
        
        # 1. API Call
        api_payload = {
            "user_id": "mlx_benchmark",
            "session_id": str(uuid.uuid4()),
            "product_name": normalized_input.get("product_name", ""),
            "ingredients_text": normalized_input.get("ingredient_text", ""),
            "warning_text": normalized_input.get("warning_text", ""),
            "region": normalized_input.get("region", "California, USA"),
            "save_to_history": False,
        }
        api_result = call_local_api(api_payload)
        
        # 2. Compact Grounding
        try:
            from run_stage2_grounded_benchmark import compact_grounding
            grounding = compact_grounding(api_result)
        except:
            grounding = api_result

        # 3. Structuring (Stage 2)
        prompt = structure_prompt(normalized_input.get("product_name", "") + " " + normalized_input.get("ingredient_text", ""))
        struct_text = run_mlx_generation(prompt)
        parsed = extract_json_object(struct_text)
        
        # 3b. Visual Verification (v1.9)
        # We need the image paths from the case. If not available in benchmark_cases, skip.
        vlm_verified = True
        case_image_paths = case.get("image_paths", [case.get("image_path")]) if hasattr(case, "get") else []
        if case_image_paths and case_image_paths[0]:
            vlm_verified = verify_category_vlm(parsed.get("product_use_category", "unknown"), case_image_paths)
            
        # 4. Final Answer (Stage 3)
        final_prompt = final_answer_prompt(parsed, api_result)
        final_report = run_mlx_generation(final_prompt)
        
        # Scoring Stage 3 (Instruction Following)
        required_headers = ["## What I Read", "## Likely Product Category", "## Practical Recommendation"]
        headers_found = sum(1 for h in required_headers if h in final_report)
        stage3_score = headers_found / len(required_headers)
        
        case_duration = time.time() - case_start
        
        # Scoring Stage 2 (Structuring)
        truth = STAGE2_TRUTH.get(case_id, {})
        cat_correct = category_score(parsed.get("product_use_category", ""), truth.get("product_use_category", ""))
        mat_correct = material_score(parsed.get("material_or_form", ""), truth.get("material_or_form", ""))
        priority_correct = info_priority_score(parsed.get("information_priority", ""), truth.get("information_priority", ""))
        
        results.append({
            "case_id": case_id,
            "duration_sec": round(case_duration, 2),
            "stage1_ocr_score": 1.0, 
            "stage2_cat_correct": cat_correct,
            "stage2_mat_correct": mat_correct,
            "stage2_priority_correct": priority_correct,
            "stage3_instruction_score": stage3_score,
            "parsed": parsed,
            "final_report": final_report
        })

    total_duration = time.time() - start_time
    
    summary = {
        "provider": "mlx",
        "case_count": len(results),
        "total_duration_sec": round(total_duration, 2),
        "mean_category_correct": round(mean(r["stage2_cat_correct"] for r in results), 4) if results else 0,
        "mean_material_correct": round(mean(r["stage2_mat_correct"] for r in results), 4) if results else 0,
        "mean_priority_correct": round(mean(r["stage2_priority_correct"] for r in results), 4) if results else 0,
        "mean_stage3_instruction_score": round(mean(r["stage3_instruction_score"] for r in results), 4) if results else 0,
    }

    (output_dir / "stage2_grounded_results_mlx.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    (output_dir / "stage2_grounded_summary_mlx.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    
    print(f"Grounded Benchmarks complete. Output: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MLX Gemma 4 Benchmarking Suite")
    parser.add_argument("--mode", choices=["ocr", "grounded", "both"], default="both")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip-ocr", action="store_true", help="Skip OCR stage if already run")
    parser.add_argument("--tiled", action="store_true", help="Enable high-resolution tiling")
    parser.add_argument("--hybrid", action="store_true", help="Enable v3.0 Hybrid OCR (Native + Gemma)")
    args = parser.parse_args()

    if args.mode in ["ocr", "both"] and not args.skip_ocr:
        # Pass both flags, though run_ocr_benchmarks might need to handle hybrid specifically
        run_ocr_benchmarks(args.limit, tiled=args.tiled, hybrid=args.hybrid)
    if args.mode in ["grounded", "both"]:
        run_grounded_benchmarks(args.limit)
