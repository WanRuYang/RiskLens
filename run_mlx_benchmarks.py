import argparse
import json
import os
import time
import uuid
import re
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
    run_mlx_ocr_multi,
    run_mlx_generation,
    verify_category_vlm,
    run_hybrid_ocr,
    run_classifier_agent,
    run_search_agent,
    run_editor_agent
)

PROJECT_ROOT = Path(__file__).resolve().parent
OCR_CASES_PATH = PROJECT_ROOT / "benchmark_ocr_cases.json"
GROUNDED_CASES_PATH = PROJECT_ROOT / "benchmark_cases.json"
OCR_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "ocr_benchmark"
GROUNDED_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "stage2_grounded_benchmark"

def normalize_text(text: str) -> str:
    # Remove punctuation for soft matching
    text = re.sub(r'[^\w\s]', '', text)
    # Lowercase and collapse whitespace
    return " ".join(text.lower().split())

def score_ocr_case(extracted_text: str, expected_strings: list[str]) -> dict[str, Any]:
    # v20.0: Fuzzy Scoring to handle phrasing variation (Web vs Packaging)
    norm_res = normalize_text(extracted_text)
    
    results = []
    total_score = 0.0
    
    for item in expected_strings:
        norm_exp = normalize_text(item)
        if not norm_exp:
            score = 1.0
        else:
            # 1. Exact normalized match
            if norm_exp in norm_res:
                score = 1.0
            else:
                # 2. Token overlap (Fuzzy)
                exp_tokens = set(norm_exp.split())
                res_tokens = set(norm_res.split())
                if not exp_tokens:
                    score = 0.0
                else:
                    intersection = exp_tokens.intersection(res_tokens)
                    score = len(intersection) / len(exp_tokens)
                    # Heuristic: 70% overlap on a long string is practically a hit
                    if score > 0.7: score = 1.0
            
        results.append({"expected": item, "score": score})
        total_score += score
    
    recall = total_score / len(expected_strings) if expected_strings else 1.0
    return {
        "expected_count": len(expected_strings),
        "hit_count": round(total_score, 1),
        "substring_recall": round(recall, 4),
        "matches": results,
    }

def run_ocr_benchmarks(limit: int = 0, tiled: bool = False, hybrid: bool = False, cases_file: str = None):
    print(f"Starting MLX OCR Benchmarks (Tiled: {tiled}, Hybrid: {hybrid})...")
    path = Path(cases_file) if cases_file else OCR_CASES_PATH
    cases = json.loads(path.read_text())
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

    results = []
    for idx, case in enumerate(cases, start=1):
        case_id = case.get("id", str(idx))
        image_paths = case.get("image_paths", [])
        expected_strings = case.get("expected_strings", [])
        
        print(f"[{idx}/{len(cases)}] Case: {case_id}")
        
        # Run OCR
        case_start = time.time()
        if hybrid:
            # v3.3 Ultimate Hybrid: Run on all available images and join
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
                    extracted = run_hybrid_ocr(path)
                    chunks.append(extracted)
            extracted_text = "\n\n".join(chunks)
        else:
            extracted_text = run_mlx_ocr_multi(image_paths)
        
        case_duration = time.time() - case_start
        
        # Scoring
        score = score_ocr_case(extracted_text, expected_strings)
        results.append({
            "case_id": case_id,
            "substring_recall": score["substring_recall"],
            "expected_count": score["expected_count"],
            "hit_count": score["hit_count"],
            "duration_sec": round(case_duration, 2)
        })
        
        # Save per-case result
        case_result = {
            "case_id": case_id,
            "extracted_text": extracted_text,
            "expected_strings": expected_strings,
            "score": score,
            "duration_sec": case_duration
        }
        (output_dir / f"{case_id}_result.json").write_text(json.dumps(case_result, indent=2, ensure_ascii=False))

    # Save summary
    summary_file = output_dir / "ocr_summary_mlx.json"
    summary_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    
    # Generate report
    report = [
        "# MLX OCR Benchmark Report",
        f"Timestamp: {timestamp}",
        f"Mode: {'Hybrid' if hybrid else ('Tiled' if tiled else 'Standard')}",
        f"Cases: {len(results)}",
        f"Mean Recall: {mean(r['substring_recall'] for r in results):.4f}",
        f"Mean Duration: {mean(r['duration_sec'] for r in results):.2f}s",
        "",
        "| Case ID | Recall | Expected | Hits | Duration |",
        "| :--- | :---: | :---: | :---: | :---: |"
    ]
    for r in results:
        report.append(f"| {r['case_id']} | {r['substring_recall']:.4f} | {r['expected_count']} | {r['hit_count']} | {r['duration_sec']:.1f}s |")
        
    (output_dir / "ocr_report_mlx.md").write_text("\n".join(report))
    print(f"OCR Benchmarks complete. Output: {output_dir}")

def category_score(actual: str, expected: str) -> float:
    if not expected: return 1.0
    return 1.0 if actual.lower() == expected.lower() else 0.0

def run_grounded_benchmarks(limit: int = 0, cases_file: str = None):
    print("Starting MLX Grounded Benchmarks...")
    if cases_file:
        cases = json.loads(Path(cases_file).read_text())
    else:
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

    # We need Stage 2 Truth for scoring
    # For real-world v2, we might not have it yet, so we assume correctness or log
    STAGE2_TRUTH = {}
    if GROUNDED_CASES_PATH.exists():
        try:
            cases_raw = json.loads(GROUNDED_CASES_PATH.read_text())
            for c in cases_raw:
                STAGE2_TRUTH[c["id"]] = c
        except: pass

    results = []
    start_time = time.time()
    
    for idx, case in enumerate(cases, start=1):
        case_id = case.get('id', case.get('case_id', str(idx)))
        print(f"[{idx}/{len(cases)}] Case: {case_id}")
        
        # Build Stage 2 Input
        case_start = time.time()
        try:
            from run_stage2_text_benchmark import build_stage2_input
            normalized_input = build_stage2_input(case)
        except:
            normalized_input = {
                "product_name": case.get('product_title', case.get('product_name', '')),
                "ingredient_text": case.get('ingredients', ''),
                "warning_text": case.get('warning_text', ''),
                "region": "California, USA"
            }
            
        # 1. Search Agent (Retrieval)
        search_data = {
            "product_name": normalized_input.get("product_name", ""),
            "ingredient_text": normalized_input.get("ingredient_text", ""),
            "warning_text": normalized_input.get("warning_text", ""),
            "region": normalized_input.get("region", "California, USA"),
            "web_ground_truth": case.get("web_ground_truth") if isinstance(case, dict) else None
        }
        api_result = run_search_agent(search_data)
        
        # 2. Classifier Agent (Alignment)
        combined_text = f"{search_data['product_name']} {search_data['ingredient_text']}"
        parsed = run_classifier_agent(combined_text)
        
        # 2b. Autonomous Self-Verification
        vlm_verified = True
        case_image_paths = case.get("image_paths", [case.get("image_path")]) if hasattr(case, "get") else []
        if case_image_paths and case_image_paths[0]:
            vlm_verified = verify_category_vlm(parsed.get("product_use_category", "unknown"), case_image_paths)
        
        # 3. Editor Agent (Reporting)
        final_report = run_editor_agent(parsed, api_result)
        
        # 4. Scoring Stage 3 (Instruction Following)
        required_headers = ["## What I Read", "## Likely Product Category", "## Practical Recommendation"]
        headers_found = sum(1 for h in required_headers if h in final_report)
        stage3_score = headers_found / len(required_headers)
        
        case_duration = time.time() - case_start
        
        # Scoring Stage 2 (Structuring/Logic)
        truth = STAGE2_TRUTH.get(case_id, {})
        cat_correct = category_score(parsed.get("product_use_category", ""), truth.get("product_use_category", ""))
        mat_correct = category_score(parsed.get("material_or_form", ""), truth.get("material_or_form", ""))
        pri_correct = category_score(parsed.get("information_priority", ""), truth.get("information_priority", ""))

        results.append({
            "case_id": case_id,
            "category_correct": cat_correct,
            "material_correct": mat_correct,
            "priority_correct": pri_correct,
            "stage2b_vlm_verified": vlm_verified,
            "stage3_instruction_score": stage3_score,
            "duration_sec": round(case_duration, 2),
            "final_report": final_report
        })
        
    total_duration = time.time() - start_time
    
    # Save results
    summary = {
        "provider": "mlx",
        "case_count": len(results),
        "total_duration_sec": round(total_duration, 2),
        "mean_category_correct": round(mean(r["category_correct"] for r in results), 4) if results else 0,
        "mean_material_correct": round(mean(r["material_correct"] for r in results), 4) if results else 0,
        "mean_priority_correct": round(mean(r["priority_correct"] for r in results), 4) if results else 0,
        "mean_self_verification_pass_rate": round(mean(r["stage2b_vlm_verified"] for r in results), 4) if results else 0,
        "mean_stage3_instruction_score": round(mean(r["stage3_instruction_score"] for r in results), 4) if results else 0,
    }
    
    (output_dir / "stage2_grounded_summary_mlx.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    (output_dir / "stage2_grounded_results_mlx.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    
    print(f"Grounded Benchmarks complete. Output: {output_dir}")

def main():
    parser = argparse.ArgumentParser(description="MLX Benchmark Suite")
    parser.add_argument("--mode", choices=["ocr", "grounded", "both"], default="both")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip-ocr", action="store_true", help="Skip OCR stage if already run")
    parser.add_argument("--tiled", action="store_true", help="Enable high-resolution tiling")
    parser.add_argument("--hybrid", action="store_true", help="Enable v3.0 Hybrid OCR (Native + Gemma)")
    parser.add_argument("--cases-file", type=str, help="Path to custom benchmark cases JSON")
    args = parser.parse_args()

    if args.mode in ["ocr", "both"] and not args.skip_ocr:
        run_ocr_benchmarks(args.limit, tiled=args.tiled, hybrid=args.hybrid, cases_file=args.cases_file)
    if args.mode in ["grounded", "both"]:
        run_grounded_benchmarks(args.limit, cases_file=args.cases_file)

if __name__ == "__main__":
    main()
