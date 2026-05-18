import time
import json
from pathlib import Path
from mlx_engine import (
    run_scribe_agent,
    run_classifier_agent,
    run_search_agent,
    run_editor_agent
)

PROJECT_ROOT = Path(__file__).resolve().parent
TEST_IMAGE = str(PROJECT_ROOT / "benchmark_images/weee_001/front.png")
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "profiling"

def benchmark_agentic_flow():
    print("=== Starting Full Agentic Flow Performance Test (M4 Mac) ===")
    
    metrics = {}
    overall_start = time.time()
    
    # 1. Scribe Agent (Vision/OCR)
    print("1. Running Scribe Agent...")
    start = time.time()
    ocr_text = run_scribe_agent([TEST_IMAGE], mode="hybrid")
    metrics["scribe_sec"] = round(time.time() - start, 2)
    
    # 2. Classifier Agent (Logic)
    print("2. Running Classifier Agent...")
    start = time.time()
    classification = run_classifier_agent(ocr_text)
    metrics["classifier_sec"] = round(time.time() - start, 2)
    
    # 3. Search Agent (DB)
    print("3. Running Search Agent...")
    start = time.time()
    search_data = {
        "product_name": classification.get("product_name", "Test Product"),
        "ingredient_text": classification.get("ingredient_text", ""),
        "warning_text": classification.get("warning_text", ""),
        "region": "California, USA"
    }
    api_result = run_search_agent(search_data)
    metrics["search_sec"] = round(time.time() - start, 2)
    
    # 4. Editor Agent (Reporting)
    print("4. Running Editor Agent...")
    start = time.time()
    _ = run_editor_agent(classification, api_result)
    metrics["editor_sec"] = round(time.time() - start, 2)
    
    overall_duration = time.time() - overall_start
    metrics["total_duration_sec"] = round(overall_duration, 2)
    
    print("\n" + "="*40)
    print(" AGENTIC FLOW PERFORMANCE SUMMARY")
    print("="*40)
    for agent, duration in metrics.items():
        print(f"{agent:20}: {duration}s")
    print("="*40)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "agentic_flow_profile.json"
    output_file.write_text(json.dumps(metrics, indent=2))
    print(f"Results saved to {output_file}")

if __name__ == "__main__":
    benchmark_agentic_flow()
