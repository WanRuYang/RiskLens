import argparse
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import mlx_vlm
import requests
from PIL import Image

from prompt_utils import extract_json_object, format_prompt

# Configuration
API_BASE_URL = os.getenv("GEMMA4GOOD_API_BASE_URL", "http://127.0.0.1:8010")
MODEL_ID = "mlx-community/gemma-4-e4b-it-4bit"
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "mlx_engine_tests"

_MODEL_CACHE: tuple[Any, Any] | None = None

def get_model():
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE
    
    print(f"Loading MLX model: {MODEL_ID}...")
    # Load model and processor with MLX
    model, processor = mlx_vlm.load(MODEL_ID)
    _MODEL_CACHE = (model, processor)
    return _MODEL_CACHE

def ocr_prompt(image_index: int = 1) -> str:
    # v1.5: Archivist Persona for absolute OCR fidelity
    return f"""
Act as a World-Class Archivist. Transcribe Image {image_index} with 100% literal accuracy.

STRUCTURE:
| Field | Content |
| :--- | :--- |
| Branding | [Product Name] |
| Ingredients | [List Chemicals Exactly] |
| Warnings | [Prop 65 / Cautions] |
| Other | [All other text] |

RULES:
- DO NOT summarize. DO NOT omit small text.
- If a chemical name is split across lines, join it.
- If text is missing, use "N/A".
"""

def structure_prompt(raw_text: str) -> str:
    # v1.5: Ontology-Guided Structuring (Strict Rules)
    instructions = """
You are a Safety Data Architect. Map the OCR text to the safety ontology below.

ONTOLOGY RULES:
1. CATEGORY:
   - food: Ingestible items, snacks, pantry.
   - dietary_supplement: Vitamins, powders, herbs.
   - food_contact: Plates, cups, mugs, cutlery.
   - household_cleaner: Sprays, detergents, soaps.
   - children_product: Items for kids < 12 (toys, bibs).
   - electronics: Devices, cables, chargers.
   - other: Default.
2. PRIORITY:
   - ingredient_first: If category is food, supplement, cleaner, or cosmetic.
   - material_first: If category is food_contact, children_product, or electronics.

Return ONLY valid JSON:
{
  "logic_check": "Justify category/priority based on rules above",
  "product_name": "...",
  "ingredient_text": "...",
  "warning_text": "...",
  "product_use_category": "[Value from ONTOLOGY]",
  "material_or_form": "...",
  "information_priority": "[Value from ONTOLOGY]",
  "confidence": 0.0-1.0
}
"""
    return format_prompt(
        task_name="Structure OCR output v1.5 (Ontology)",
        instructions=instructions,
        payload=raw_text,
        include_category_reference=True,
    )

def final_answer_prompt(structured_ocr: dict[str, Any], api_result: dict[str, Any]) -> str:
    instructions = """
You are writing the final consumer-facing answer for a local safety assistant.

Use the grounded retrieval result below. Do not invent sources.
Be careful not to treat a warning or hazard listing as proof that the product is unsafe.
If the product has a use-with-protection style warning, mention that separately from regulatory warnings.

Apply the category rule explicitly:
- If this is food or a household cleaner, say that ingredients matter most.
- If ingredients are missing or vague for those categories, say that a stronger answer would require the ingredient list.
- If this is another category, say that material or construction matters most.
- If the material is unclear for those categories, say that a stronger answer would require knowing what it is made of.
- If a product page link is provided, treat it as supporting context for product type or brand clues, not as proof of the exact ingredient list.

Write in Markdown with these sections:
## What I Read
## Likely Product Category
## Potential Chemicals of Concern
## Sources and Regions
## Practical Recommendation
Provide a clear, actionable recommendation based on the grounded evidence and the guidance bucket. Explain why this choice is made.
## Repeated Exposure Note
## Important Caveat

Recommendation buckets should be interpreted as:
- opt_for_other_product
- rare_use_may_be_okay_but_limit_repeated_exposure
- emerging_research_caution
- limited_signal_found
"""
    payload = "\n\n".join(
        [
            "Structured OCR:",
            json.dumps(structured_ocr, ensure_ascii=False, indent=2),
            "Grounded API result:",
            json.dumps(api_result, ensure_ascii=False, indent=2),
        ]
    )
    return format_prompt(
        task_name="Write final grounded answer",
        instructions=instructions,
        payload=payload,
        include_category_reference=True,
    )

def call_local_api(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.post(f"{API_BASE_URL}/analyze-product", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error calling local API: {e}")
        return {"error": str(e), "hits": []}

def ocr_prompt(image_index: int = 1) -> str:
    # v2.0: Restoring the Peak Recall persona from v1.1
    return f"""
Analyze Image {image_index} and extract all visible text faithfully. 
You are an expert transcriber. Be extremely precise with chemical and ingredient names.

Use these headers:
# PRODUCT NAME
# INGREDIENTS
# WARNINGS & SAFETY
# OTHER TEXT

Rules:
- Transcription must be literal and faithful.
- If a section is missing, write "(None visible)".
- Do not summarize. Preserve line breaks.
"""

def structure_prompt(raw_text: str) -> str:
    # v2.0: Unified CoT + Decision Tree + Direct Ontology Injection
    instructions = """
You are a Safety Data Architect. Step-by-step, map the OCR text to the ontology below.

DECISION TREE:
1. Ingredients? (YES: Ingestible=food, Non-ingestible=household_cleaner)
2. Food-contact items (cups, mugs)? (YES=food_contact)
3. For kids (toys, bibs)? (YES=children_product)
4. Electronics? (YES=electronics)
5. Else -> other.

ONTOLOGY DEFINITIONS:
- food: Ingestible items, snacks.
- dietary_supplement: Vitamins, herbs.
- household_cleaner: Sprays, soaps.
- children_product: Items for kids < 12.
- food_contact: Plates, cups, cutlery.

Return ONLY valid JSON:
{
  "reasoning": "Explain the decision path taken",
  "product_name": "...",
  "ingredient_text": "...",
  "warning_text": "...",
  "product_use_category": "[Value from Tree]",
  "material_or_form": "...",
  "information_priority": "ingredient_first OR material_first"
}
"""
    return format_prompt(
        task_name="Structure OCR output v2.0 (Unified)",
        instructions=instructions,
        payload=raw_text,
        include_category_reference=True,
    )

def run_mlx_ocr(image_path: str) -> str:
    model, processor = get_model()
    
    messages = [
        {"role": "user", "content": [
            {"type": "image"},
            {"type": "text", "text": ocr_prompt()}
        ]}
    ]
    
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    
    extracted = mlx_vlm.generate(
        model, 
        processor, 
        prompt, 
        image_path, 
        max_tokens=1000,
        temperature=0.1
    )
    if hasattr(extracted, "text"):
        return extracted.text.strip()
    return str(extracted).strip()

def verify_category_vlm(category: str, image_paths: list[str]) -> bool:
    # v1.9: Visual Second Opinion
    model, processor = get_model()
    valid_paths = [p for p in image_paths if p]
    if not valid_paths: return True
    
    prompt_text = f"The system classified this product as '{category}'. Looking at the visual evidence, is this correct? Answer only YES or NO."
    
    content = [{"type": "image"} for _ in range(len(valid_paths))]
    content.append({"type": "text", "text": prompt_text})
    messages = [{"role": "user", "content": content}]
    
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    
    result = mlx_vlm.generate(model, processor, prompt, valid_paths, max_tokens=10, temperature=0.0)
    text = result.text.upper() if hasattr(result, "text") else str(result).upper()
    return "YES" in text

def run_mlx_ocr_multi(image_paths: list[str]) -> str:
    # v1.7: Aggregate independent OCR results for stability
    chunks = []
    for idx, path in enumerate(image_paths, start=1):
        if path:
            extracted = run_mlx_ocr(path)
            chunks.append(f"### Image {idx}\n{extracted}")
    return "\n\n".join(chunks)

def run_mlx_generation(prompt_text: str) -> str:
    model, processor = get_model()
    
    messages = [
        {"role": "user", "content": [{"type": "text", "text": prompt_text}]}
    ]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    
    result = mlx_vlm.generate(
        model,
        processor,
        prompt,
        None, # No image
        max_tokens=800,
        temperature=0.0
    )
    if hasattr(result, "text"):
        return result.text.strip()
    return str(result).strip()

def main():
    parser = argparse.ArgumentParser(description="MLX Gemma 4 Engine for OCR and Grounded Safety")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # test-raw
    raw_parser = subparsers.add_parser("test-raw", help="Run OCR on an image")
    raw_parser.add_argument("image", type=str, help="Path to the image file")

    # test-grounded
    grounded_parser = subparsers.add_parser("test-grounded", help="Run full grounded pipeline")
    grounded_parser.add_argument("image", type=str, help="Path to the image file")
    grounded_parser.add_argument("--region", type=str, default="California, USA", help="Region for grounding")
    grounded_parser.add_argument("--url", type=str, default="", help="Optional product page URL")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.command == "test-raw":
        print(f"Running OCR on {args.image}...")
        extracted_text = run_mlx_ocr(args.image)
        
        output_file = OUTPUT_DIR / f"test_raw_{timestamp}_mlx.txt"
        output_file.write_text(extracted_text)
        
        print("\n--- Extracted Text ---")
        print(extracted_text)
        print("----------------------")
        print(f"Saved to {output_file}")

    elif args.command == "test-grounded":
        print(f"Running grounded pipeline for {args.image}...")
        
        # 1. OCR
        raw_ocr_text = run_mlx_ocr(args.image)
        
        # 2. Structure
        structured_text = run_mlx_generation(structure_prompt(raw_ocr_text))
        structured_ocr = extract_json_object(structured_text)
        if not structured_ocr:
            structured_ocr = {
                "product_name": "Unknown",
                "ingredient_text": raw_ocr_text,
                "warning_text": "",
                "safety_caution_text": "",
                "category_clues": "",
                "confidence_notes": "Structuring failed.",
            }
        structured_ocr["product_page_url"] = args.url

        # 3. API Call
        payload = {
            "user_id": "mlx_test_user",
            "session_id": str(uuid.uuid4()),
            "product_name": structured_ocr.get("product_name") or "Unknown Product",
            "product_page_url": args.url,
            "raw_ocr_text": raw_ocr_text,
            "ingredients_text": structured_ocr.get("ingredient_text", ""),
            "warning_text": structured_ocr.get("warning_text", ""),
            "region": args.region,
            "save_to_history": False,
        }
        api_result = call_local_api(payload)

        # 4. Final Answer
        final_report = run_mlx_generation(final_answer_prompt(structured_ocr, api_result))

        # Save results
        report_file = OUTPUT_DIR / f"test_grounded_{timestamp}_mlx.md"
        report_file.write_text(final_report)
        
        debug_file = OUTPUT_DIR / f"test_grounded_{timestamp}_debug_mlx.json"
        debug_data = {
            "raw_ocr_text": raw_ocr_text,
            "structured_ocr": structured_ocr,
            "api_result": api_result,
            "final_report": final_report
        }
        debug_file.write_text(json.dumps(debug_data, indent=2, ensure_ascii=False))

        print("\n--- Final Report ---")
        print(final_report)
        print("--------------------")
        print(f"Report saved to {report_file}")
        print(f"Debug data saved to {debug_file}")

if __name__ == "__main__":
    main()
