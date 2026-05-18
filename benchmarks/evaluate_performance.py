import json
from pathlib import Path
import re

def normalize_text(text: str) -> str:
    text = re.sub(r'[^\w\s]', '', text)
    return " ".join(text.lower().split())

def calculate_recall(extracted: str, expected_list: list[str]) -> float:
    norm_res = normalize_text(extracted)
    scores = []
    for item in expected_list:
        norm_exp = normalize_text(item)
        if not norm_exp:
            scores.append(1.0)
            continue
        if norm_exp in norm_res:
            scores.append(1.0)
        else:
            exp_tokens = set(norm_exp.split())
            res_tokens = set(norm_res.split())
            if not exp_tokens:
                scores.append(0.0)
            else:
                intersection = exp_tokens.intersection(res_tokens)
                scores.append(len(intersection) / len(exp_tokens))
    return sum(scores) / len(expected_list) if expected_list else 1.0

def run_evaluation():
    PROJECT_ROOT = Path(__file__).resolve().parent
    OPENAI_JSON = PROJECT_ROOT / "benchmark_ocr_real_cases_v2_openai.json"
    
    # 1. Load Ground Truth
    if not OPENAI_JSON.exists():
        print("Waiting for OpenAI labeling...")
        return
        
    cases = json.loads(OPENAI_JSON.read_text())
    cases = [c for c in cases if "openai_ground_truth" in c]
    print(f"Evaluating {len(cases)} cases...")
    
    # 2. Get latest Raw Gemma Results
    raw_dirs = sorted((PROJECT_ROOT / "outputs" / "raw_gemma4_benchmark").glob("2026*"), reverse=True)
    raw_results = {}
    if raw_dirs:
        raw_file = raw_dirs[0] / "raw_results.json"
        if raw_file.exists():
            for r in json.loads(raw_file.read_text()):
                raw_results[r["case_id"]] = r["extracted"]

    # 3. Get latest Optimized Results (Agentic)
    opt_dirs = sorted((PROJECT_ROOT / "outputs" / "ocr_benchmark").glob("*_hybrid_mlx"), reverse=True)
    opt_results = {}
    if opt_dirs:
        # Note: the ocr_benchmark saves per-case result.json files or a summary
        # Let's check for the summary first
        summary_file = opt_dirs[0] / "ocr_outputs_mlx.json"
        if summary_file.exists():
            data = json.loads(summary_file.read_text())
            for cid, r in data.items():
                opt_results[cid] = r.get("extracted_text", "")

    # 4. Score
    comparison = []
    for c in cases:
        cid = c["id"]
        expected = c["expected_strings"]
        
        raw_extracted = raw_results.get(cid, "")
        opt_extracted = opt_results.get(cid, "")
        
        comparison.append({
            "case_id": cid,
            "raw_recall": calculate_recall(raw_extracted, expected) if raw_extracted else 0.0,
            "opt_recall": calculate_recall(opt_extracted, expected) if opt_extracted else 0.0
        })
        
    # 5. Summarize
    if comparison:
        mean_raw = sum(c["raw_recall"] for c in comparison) / len(comparison)
        mean_opt = sum(c["opt_recall"] for c in comparison) / len(comparison)
        
        print("\n" + "="*50)
        print(" HEAD-TO-HEAD: RAW GEMMA 4 vs. OPTIMIZED PEAK (v26.1)")
        print("="*50)
        print(f" Cases Evaluated: {len(comparison)}")
        print(f" Raw Gemma 4 Recall: {mean_raw:.2%}")
        print(f" Optimized Version:  {mean_opt:.2%}")
        print(f" Improvement:        {mean_opt - mean_raw:+.2%}")
        print("="*50)

if __name__ == "__main__":
    run_evaluation()
