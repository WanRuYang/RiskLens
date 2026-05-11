import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

OPENAI_MODEL = "gpt-4o-mini"
OPENAI_URL = "https://api.openai.com/v1/chat/completions" # Note: standard endpoint
OPENAI_KEY_PATH = Path.home() / ".ssh" / "openai_api_key.txt"

def load_key():
    return OPENAI_KEY_PATH.read_text(encoding="utf-8").strip()

def image_to_base64(path):
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")

def get_openai_labels(image_paths, api_key):
    content = [
        {"type": "text", "text": "Extract literal safety data from these product images. Return ONLY JSON with: product_name, ingredient_text, warning_text."}
    ]
    for path in image_paths:
        if Path(path).exists():
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_to_base64(path)}"}
            })
            
    payload = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": content}],
        "response_format": {"type": "json_object"}
    }
    
    req = urllib.request.Request(
        OPENAI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        return json.loads(body["choices"][0]["message"]["content"])

def main():
    api_key = load_key()
    PROJECT_ROOT = Path(__file__).resolve().parent
    INPUT_JSON = PROJECT_ROOT / "benchmark_ocr_real_cases_v2.json"
    OUTPUT_JSON = PROJECT_ROOT / "benchmark_ocr_real_cases_v2_openai.json"
    
    cases = json.loads(INPUT_JSON.read_text())
    print(f"Labeling {len(cases)} cases with OpenAI...")
    
    for idx, case in enumerate(cases):
        if "openai_ground_truth" in case:
            continue
            
        print(f"[{idx+1}/{len(cases)}] Labeling {case['id']}...")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                labels = get_openai_labels(case["image_paths"], api_key)
                case["openai_ground_truth"] = labels
                case["expected_strings"] = [labels.get("product_name", ""), labels.get("ingredient_text", "")]
                if labels.get("warning_text"):
                    case["expected_strings"].append(labels["warning_text"])
                break
            except Exception as e:
                print(f"  Attempt {attempt+1} failed for {case['id']}: {e}")
                time.sleep(10 * (attempt + 1))
        
        # Throttling
        time.sleep(2)
            
        if (idx + 1) % 10 == 0:
            OUTPUT_JSON.write_text(json.dumps(cases, indent=2, ensure_ascii=False))
            print(f"  Checkpoint: {idx+1} cases saved.")
            
    OUTPUT_JSON.write_text(json.dumps(cases, indent=2, ensure_ascii=False))
    print(f"Saved OpenAI-labeled cases to {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
