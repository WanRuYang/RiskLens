import argparse
import json
import os
import time
from pathlib import Path
from statistics import mean
from typing import Any

import mlx_vlm
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_ID = "mlx-community/gemma-4-e4b-it-4bit"
OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "raw_gemma4_benchmark"

def run_raw_vlm(image_path: str, prompt: str) -> str:
    model, processor = mlx_vlm.load(MODEL_ID)
    
    # Raw Gemma 4 usually takes a simple chat format
    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
    prompt_text = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    
    result = mlx_vlm.generate(model, processor, prompt_text, image_path, max_tokens=1000, temperature=0.0)
    if hasattr(result, "text"):
        return result.text.strip()
    return str(result).strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-file", type=str, default="benchmark_ocr_real_cases_v2_openai.json")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    
    cases_path = PROJECT_ROOT / args.cases_file
    if not cases_path.exists():
        print(f"Cases file {args.cases_file} not found. Waiting for labeling...")
        return
        
    cases = json.loads(cases_path.read_text())
    if args.limit > 0:
        cases = cases[:args.limit]
        
    print(f"Starting RAW GEMMA 4 Benchmark (Limit: {args.limit})...")
    
    results = []
    output_dir = OUTPUT_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for idx, case in enumerate(cases, start=1):
        print(f"[{idx}/{len(cases)}] Processing {case['id']}...")
        image_path = case["image_paths"][0] # Front only for raw test
        
        prompt = "Transcribe the product name, ingredients, and any safety warnings from this image. Return only the transcription."
        
        start = time.time()
        extracted = run_raw_vlm(image_path, prompt)
        duration = time.time() - start
        
        results.append({
            "case_id": case["id"],
            "extracted": extracted,
            "duration": duration
        })
        
    (output_dir / "raw_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Benchmark complete. Results saved to {output_dir}")

if __name__ == "__main__":
    from datetime import datetime
    main()
