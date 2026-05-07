import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
OCR_CASES_PATH = PROJECT_ROOT / "benchmark_ocr_cases.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "finetuning"
OUTPUT_FILE = OUTPUT_DIR / "vision_alignment_v1.jsonl"

def build_vision_dataset():
    if not OCR_CASES_PATH.exists():
        print("Error: benchmark_ocr_cases.json not found.")
        return
        
    cases = json.loads(OCR_CASES_PATH.read_text())
    dataset = []
    
    print(f"Generating vision-language pairs for {len(cases)} cases...")
    
    for case in cases:
        image_paths = case.get("image_paths", [case.get("image_path")])
        expected = " ".join(case.get("expected_strings", []))
        
        # We create a record for each image in the case
        for path in image_paths:
            if not path: continue
            
            # mlx-vlm expects this format for image-text fine-tuning
            dataset.append({
                "image": path,
                "conversations": [
                    {
                        "role": "user",
                        "content": "<image>\nExtract all text from this product label precisely."
                    },
                    {
                        "role": "assistant",
                        "content": f"Literal Transcription:\n{expected}"
                    }
                ]
            })

    print(f"Writing {len(dataset)} vision pairs to {OUTPUT_FILE}...")
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for entry in dataset:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    build_vision_dataset()
