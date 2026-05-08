import argparse
import json
import os
import uuid
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import mlx_vlm
import requests
from PIL import Image

from prompt_utils import extract_json_object, format_prompt
from vision_utils import get_tiles, save_tiles
from safety_lookup import SafetyKnowledgeBase

# Configuration
API_BASE_URL = os.getenv("GEMMA4GOOD_API_BASE_URL", "http://127.0.0.1:8010")
MODEL_ID = "mlx-community/gemma-4-e4b-it-4bit"
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "mlx_engine_tests"

_MODEL_CACHE: tuple[Any, Any] | None = None
_KB_CACHE: SafetyKnowledgeBase | None = None

def get_model():
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE
    
    adapter_path = PROJECT_ROOT / "adapters"
    
    print(f"Loading MLX model: {MODEL_ID}...")
    if adapter_path.exists():
        print(f"  --> FOUND LORA ADAPTER at {adapter_path}. Loading merged model...")
        model, processor = mlx_vlm.load(MODEL_ID, adapter_path=str(adapter_path))
    else:
        print("  (No LoRA adapter found, loading base model)")
        model, processor = mlx_vlm.load(MODEL_ID)
        
    _MODEL_CACHE = (model, processor)
    return _MODEL_CACHE

def get_kb() -> SafetyKnowledgeBase:
    global _KB_CACHE
    if _KB_CACHE is None:
        print("Initializing Native Forensic Knowledge Base...")
        _KB_CACHE = SafetyKnowledgeBase()
    return _KB_CACHE

# --- Prompts ---

def ocr_prompt(image_index: int = 1) -> str:
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

def final_answer_prompt(structured_ocr: dict[str, Any], api_result: dict[str, Any]) -> str:
    instructions = """
You are writing the final consumer-facing answer for a local safety assistant.

Use the grounded retrieval result below. Do not invent sources.

Write in Markdown with these sections:
## What I Read
## Likely Product Category
## Potential Chemicals of Concern
## Sources and Regions
## Practical Recommendation
Provide a clear, actionable recommendation based on the grounded evidence and the guidance bucket.
## Repeated Exposure Note
## Important Caveat
"""
    payload = "\n\n".join([
        "Structured OCR:",
        json.dumps(structured_ocr, ensure_ascii=False, indent=2),
        "Grounded API result:",
        json.dumps(api_result, ensure_ascii=False, indent=2),
    ])
    return format_prompt(
        task_name="Write final grounded answer",
        instructions=instructions,
        payload=payload,
        include_category_reference=True,
    )

# --- Core Inference Functions ---

def run_mlx_generation(prompt_text: str) -> str:
    model, processor = get_model()
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt_text}]}]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    result = mlx_vlm.generate(model, processor, prompt, None, max_tokens=1000, temperature=0.0)
    if hasattr(result, "text"):
        return result.text.strip()
    return str(result).strip()

def run_native_ocr(image_path: str) -> str:
    try:
        result = subprocess.run(["swift", "native_ocr.swift", image_path], capture_output=True, text=True, timeout=10)
        return result.stdout.strip()
    except Exception as e:
        print(f"Native OCR failed: {e}")
        return ""

def run_hybrid_ocr(image_path: str, grid=(2, 2)) -> str:
    print(f"Running v3.3 Ultimate Hybrid OCR for {Path(image_path).name}...")
    try:
        raw_native_text = run_native_ocr(image_path)
        
        temp_dir = PROJECT_ROOT / "outputs" / "temp_tiles"
        tiles = get_tiles(image_path, grid=grid, enhance=True)
        tile_paths = save_tiles(tiles, temp_dir, Path(image_path).stem)
        
        model, processor = get_model()
        num_tiles = len(tile_paths)
        
        # v3.3: Ultimate Hybrid (Contextual Tiling + Native OCR Hints)
        prompt_text = f"""
Analyze these {num_tiles} high-resolution images of a product label. 
Hardware OCR hints:
{raw_native_text}

TASK:
Perform a character-perfect transcription of EVERY WORD. Use hints to resolve blurry areas.
Literal transcription only. No filler.
"""
        content = [{"type": "image"} for _ in range(num_tiles)]
        content.append({"type": "text", "text": prompt_text})
        messages = [{"role": "user", "content": content}]
        prompt = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
        
        # Explicitly handle multi-image generation with error catch
        extracted = mlx_vlm.generate(model, processor, prompt, tile_paths, max_tokens=2500, temperature=0.0)
        return extracted.text.strip() if hasattr(extracted, "text") else str(extracted).strip()
        
    except Exception as e:
        print(f"  Hybrid OCR failed for {image_path}: {e}")
        print("  Falling back to standard OCR...")
        try:
            return run_mlx_ocr(image_path)
        except:
            return run_native_ocr(image_path) or "OCR Error"

def run_mlx_ocr(image_path: str) -> str:
    # v1.1 Persona for reliable fallback
    model, processor = get_model()
    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": ocr_prompt()}]}]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    result = mlx_vlm.generate(model, processor, prompt, image_path, max_tokens=1000, temperature=0.1)
    if hasattr(result, "text"):
        return result.text.strip()
    return str(result).strip()

def run_scribe_agent(image_paths: list[str], mode: str = "hybrid") -> str:
    """Agent 1: The Scribe - Extracts text from images."""
    if mode == "hybrid":
        chunks = []
        for path in image_paths[:3]:
            if path: chunks.append(run_hybrid_ocr(path))
        return "\n\n".join(chunks)
    return "No OCR mode selected."

def run_web_scribe_agent(url: str) -> str:
    """Agent 1b: The Web Scribe - Deep marketplace parsing."""
    print(f"Forensic Link Scan: {url}...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, timeout=15, headers=headers)
        if response.status_code != 200:
            return f"Forensic Alert: Unreachable ({response.status_code})."

        html = response.text
        domain = url.split('/')[2]
        
        # 1. Unified Metadata Extraction
        title = re.search(r'property="og:title"\s+content="(.*?)"', html, re.I)
        desc = re.search(r'property="og:description"\s+content="(.*?)"', html, re.I)
        
        title_val = title.group(1) if title else "Unknown Product"
        desc_val = desc.group(1) if desc else ""

        # 2. Specialized Retailer Logic (Asian Marketplaces)
        # Weee! / Ranch 99 often use specific div classes for ingredients
        ingredients = ""
        if "sayweee" in domain or "99ranch" in domain:
            # Look for common ingredient containers
            ing_match = re.search(r'(?:Ingredients|Componenti):\s*(.*?)(?:</|Nutrition)', html, re.I | re.S)
            if ing_match:
                ingredients = ing_match.group(1).strip()

        info = f"SOURCE: {domain}\nPRODUCT: {title_val}\n"
        if ingredients:
            info += f"INGREDIENTS (Web): {ingredients[:500]}...\n"
        if desc_val:
            info += f"CONTEXT: {desc_val[:300]}..."
            
        return info

    except Exception as e:
        return f"Forensic Alert: Parsing Error ({str(e)})."

def run_classifier_agent(text: str) -> dict[str, Any]:
    """Agent 2: The Classifier - Proposes category and priority."""
    prompt = structure_prompt(text)
    raw_json = run_mlx_generation(prompt)
    return extract_json_object(raw_json)

def run_search_agent(state_data: dict[str, Any]) -> dict[str, Any]:
    """Agent 3: The Searcher - Performs native, granular database retrieval."""
    kb = get_kb()
    return kb.retrieve(state_data.get("product_name", "Unknown"), state_data.get("ingredient_text", ""), state_data.get("region", "California, USA"))

def run_editor_agent(structured_ocr: dict[str, Any], api_result: dict[str, Any]) -> str:
    """Agent 4: The Editor - Synthesizes the final report."""
    prompt = final_answer_prompt(structured_ocr, api_result)
    return run_mlx_generation(prompt)

def run_feedback_agent(user_query: str, context: dict[str, Any]) -> dict[str, Any]:
    """Agent 5: The Consultant - Forensic follow-up with granular citations."""
    api_result = context.get('api_result', {})
    kb = get_kb()
    grounding_context = kb.build_grounding_context(api_result)
    
    instructions = f"""
You are a consumer safety expert. Answer using the context below.
CONTEXT:
{grounding_context}

USER QUESTION:
{user_query}

Return ONLY valid JSON: {{"response": "...", "action": "NONE" or "RERUN_SEARCH", "action_payload": {{}}}}
"""
    raw_json = run_mlx_generation(instructions)
    return extract_json_object(raw_json)

# --- Legacy/Utility Functions ---

def call_local_api(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.post(f"{API_BASE_URL}/analyze-product", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error calling local API: {e}")
        return {"error": str(e), "hits": []}

def run_mlx_ocr_multi(image_paths: list[str]) -> str:
    chunks = []
    for idx, path in enumerate(image_paths, start=1):
        if path: chunks.append(f"### Image {idx}\n{run_hybrid_ocr(path)}")
    return "\n\n".join(chunks)

def verify_category_vlm(category: str, image_paths: list[str]) -> bool:
    model, processor = get_model()
    valid_paths = [p for p in image_paths if p]
    if not valid_paths: return True
    prompt_text = f"Is this product '{category}'? Answer YES or NO."
    messages = [{"role": "user", "content": [{"type": "image"} for _ in range(len(valid_paths))] + [{"type": "text", "text": prompt_text}]}]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    result = mlx_vlm.generate(model, processor, prompt, valid_paths, max_tokens=10, temperature=0.0)
    return "YES" in (result.text.upper() if hasattr(result, "text") else str(result).upper())

def run_tiled_ocr(image_path: str, grid=(3, 3)) -> str:
    return run_hybrid_ocr(image_path, grid=grid)

def main():
    parser = argparse.ArgumentParser(description="MLX Gemma 4 Engine for OCR and Grounded Safety")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    raw_parser = subparsers.add_parser("test-raw", help="Run OCR on an image")
    raw_parser.add_argument("image", type=str, help="Path to the image file")
    raw_parser.add_argument("--hybrid", action="store_true", help="Enable v3.0 Hybrid OCR")
    
    grounded_parser = subparsers.add_parser("test-grounded", help="Run full grounded pipeline")
    grounded_parser.add_argument("image", type=str, help="Path to the image file")
    grounded_parser.add_argument("--region", type=str, default="California, USA", help="Region")
    grounded_parser.add_argument("--hybrid", action="store_true", help="Enable v3.0 Hybrid OCR")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.command == "test-raw":
        extracted_text = run_hybrid_ocr(args.image) if args.hybrid else run_mlx_ocr_multi([args.image])
        print(f"\n--- Extracted Text ---\n{extracted_text}\n----------------------")

    elif args.command == "test-grounded":
        raw_ocr_text = run_hybrid_ocr(args.image) if args.hybrid else run_mlx_ocr_multi([args.image])
        structured_ocr = run_classifier_agent(raw_ocr_text)
        api_result = run_search_agent({"product_name": structured_ocr.get("product_name"), "ingredient_text": structured_ocr.get("ingredient_text"), "region": args.region})
        final_report = run_editor_agent(structured_ocr, api_result)
        print(f"\n--- Final Report ---\n{final_report}\n--------------------")

if __name__ == "__main__":
    main()
