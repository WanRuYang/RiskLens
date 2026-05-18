import time
import psutil
import os
import json
import threading
from pathlib import Path
from datetime import datetime
import mlx_vlm
import mlx.core as mx

# Config
MODEL_ID = "mlx-community/gemma-4-e4b-it-4bit"
PROJECT_ROOT = Path(__file__).resolve().parent
REAL_IMAGES_DIR = PROJECT_ROOT / "benchmark_images_real"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "profiling"

def get_memory_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)  # MB

def measure_cold_start():
    print("--- Measuring Cold Start ---")
    start_mem = get_memory_usage()
    start_time = time.time()
    
    model, processor = mlx_vlm.load(MODEL_ID)
    
    load_time = time.time() - start_time
    peak_mem = get_memory_usage()
    
    print(f"Model Load Time: {load_time:.2f}s")
    print(f"Memory Growth: {peak_mem - start_mem:.2f} MB")
    print(f"Current RSS: {peak_mem:.2f} MB")
    
    return {
        "load_time_sec": load_time,
        "memory_growth_mb": peak_mem - start_mem,
        "peak_rss_mb": peak_mem
    }

def measure_inference(model, processor, image_path, prompt):
    print(f"--- Measuring Inference Performance ({Path(image_path).name}) ---")
    
    # Warm up
    _ = mlx_vlm.generate(model, processor, prompt, image_path, max_tokens=10)
    
    # Actual measurement
    start_time = time.time()
    result = mlx_vlm.generate(
        model, 
        processor, 
        prompt, 
        image_path, 
        max_tokens=200,
        temperature=0.0
    )
    duration = time.time() - start_time
    
    # Approximate token count (words * 1.3 as a rough proxy if we don't count precisely)
    # Better: use length of result.text or similar
    text = result.text if hasattr(result, "text") else str(result)
    token_count = len(text.split()) * 1.3 # Very rough
    
    tps = token_count / duration
    print(f"Inference Duration: {duration:.2f}s")
    print(f"Estimated TPS: {tps:.2f}")
    
    return {
        "duration_sec": duration,
        "estimated_tps": tps,
        "output_length_chars": len(text)
    }

def stress_test_real_images(model, processor):
    print("--- Real-World Stress Test ---")
    results = []
    
    # Find some real images
    image_paths = list(REAL_IMAGES_DIR.glob("**/*.png")) + list(REAL_IMAGES_DIR.glob("**/*.jpg"))
    image_paths = image_paths[:5] # Test first 5
    
    prompt = "Extract all text from this image faithfully."
    
    for path in image_paths:
        print(f"Processing: {path.name}")
        start_mem = get_memory_usage()
        start_time = time.time()
        
        result = mlx_vlm.generate(model, processor, prompt, str(path), max_tokens=300)
        
        duration = time.time() - start_time
        peak_mem = get_memory_usage()
        
        results.append({
            "image": path.name,
            "duration_sec": duration,
            "memory_mb": peak_mem,
            "output": result.text if hasattr(result, "text") else str(result)
        })
    
    return results

def run_concurrent_test(model, processor, image_path, num_threads=2):
    print(f"--- Concurrent Throughput Test ({num_threads} threads) ---")
    prompt = "Describe this image in detail."
    
    def worker(results):
        start = time.time()
        _ = mlx_vlm.generate(model, processor, prompt, image_path, max_tokens=100)
        results.append(time.time() - start)

    threads = []
    durations = []
    for _ in range(num_threads):
        t = threading.Thread(target=worker, args=(durations,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    avg_duration = sum(durations) / len(durations)
    print(f"Avg Duration with {num_threads} threads: {avg_duration:.2f}s")
    return {"num_threads": num_threads, "avg_duration_sec": avg_duration}

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. Cold Start
    cold_start = measure_cold_start()
    
    # Load model for further tests
    model, processor = mlx_vlm.load(MODEL_ID)
    
    # 2. Inference Stats
    test_image = str(PROJECT_ROOT / "benchmark_images/weee_001/front.png")
    inference_stats = measure_inference(model, processor, test_image, "Extract text from this image.")
    
    # 3. Concurrent Test (Skipped due to threading complexities in MLX)
    concurrent_2 = {"status": "skipped"}
    
    # 4. Stress Test
    stress_results = stress_test_real_images(model, processor)
    
    # Summary
    report = {
        "timestamp": timestamp,
        "model": MODEL_ID,
        "cold_start": cold_start,
        "inference_stats": inference_stats,
        "concurrent_2_threads": concurrent_2,
        "stress_test": stress_results
    }
    
    output_file = OUTPUT_DIR / f"profile_{timestamp}.json"
    output_file.write_text(json.dumps(report, indent=2))
    print(f"\nProfiling complete. Results saved to {output_file}")

if __name__ == "__main__":
    main()
