import argparse
import json
import os
import uuid
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
import concurrent.futures
import threading
import hashlib

import mlx_vlm
import requests
from PIL import Image, ImageOps

from prompt_utils import extract_json_object, format_prompt
from vision_utils import get_tiles, save_tiles
from safety_lookup import SafetyKnowledgeBase
try:
    from semantic_store import SemanticKnowledgeStore
except ModuleNotFoundError:  # optional dependency for semantic few-shot retrieval
    SemanticKnowledgeStore = None  # type: ignore[assignment]

# Configuration
API_BASE_URL = os.getenv("GEMMA4GOOD_API_BASE_URL", "http://127.0.0.1:8010")
MODEL_ID = "mlx-community/gemma-4-e4b-it-4bit"
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "mlx_engine_tests"

_MODEL_CACHE: tuple[Any, Any] | None = None
_MODEL_CACHE_THREAD_ID: int | None = None
_MLX_LOCK = threading.RLock()
_KB_CACHE: SafetyKnowledgeBase | None = None
_SEMANTIC_STORE: Any | None = None

def get_model():
    global _MODEL_CACHE, _MODEL_CACHE_THREAD_ID
    current_thread_id = threading.get_ident()
    with _MLX_LOCK:
        if _MODEL_CACHE is not None and _MODEL_CACHE_THREAD_ID == current_thread_id:
            return _MODEL_CACHE

        if _MODEL_CACHE is not None and _MODEL_CACHE_THREAD_ID != current_thread_id:
            print("Reinitializing MLX model for the current worker thread...")
            _MODEL_CACHE = None

        adapter_path = PROJECT_ROOT / "adapters"

        print(f"Loading MLX model: {MODEL_ID}...")
        if adapter_path.exists():
            print(f"  --> FOUND LORA ADAPTER at {adapter_path}. Loading merged model...")
            model, processor = mlx_vlm.load(MODEL_ID, adapter_path=str(adapter_path))
        else:
            print("  (No LoRA adapter found, loading base model)")
            model, processor = mlx_vlm.load(MODEL_ID)

        _MODEL_CACHE = (model, processor)
        _MODEL_CACHE_THREAD_ID = current_thread_id
        return _MODEL_CACHE

def get_kb() -> SafetyKnowledgeBase:
    global _KB_CACHE
    if _KB_CACHE is None:
        print("Initializing Native Forensic Knowledge Base...")
        _KB_CACHE = SafetyKnowledgeBase()
    return _KB_CACHE

def get_semantic_store() -> Any | None:
    global _SEMANTIC_STORE
    if SemanticKnowledgeStore is None:
        print("Semantic few-shot retrieval disabled: sentence_transformers is not installed.")
        return None
    if _SEMANTIC_STORE is None:
        print("Initializing Semantic Knowledge Store (Few-Shot)...")
        _SEMANTIC_STORE = SemanticKnowledgeStore()
        _SEMANTIC_STORE.load_index()
    return _SEMANTIC_STORE

# --- Prompt Templates ---

def ocr_prompt() -> str:
    return """
You are a literal OCR transcription engine.
Transcribe EVERY WORD on this product label.
Focus on:
1. Full product name.
2. Complete ingredient list.
3. All warning text (Prop 65, safety alerts, precautions).
No commentary. No intro. No summary.
"""

def structure_prompt(raw_text: str) -> str:
    instructions = """
Clean and structure this messy OCR output.
Identify:
- product_name
- ingredient_text
- warning_text
- product_use_category (food, beverage, cosmetic, household, children, other)
- material_or_form (plastic, ceramic, metal, silicone, paper, gel, liquid, powder)
- information_priority (ingredient_first or material_first)
- reasoning (one sentence why you chose this category)

Return ONLY valid JSON.
"""
    return format_prompt(
        task_name="Structure OCR output v2.0 (Unified)",
        instructions=instructions,
        payload=raw_text,
        include_category_reference=True,
    )

def final_answer_prompt(structured_ocr: dict[str, Any], api_result: dict[str, Any]) -> str:
    # v21.0: Dynamically include analogous cases for few-shot reasoning
    analogous = api_result.get("analogous_cases", [])
    few_shot_block = ""
    if analogous:
        few_shot_block = "\n\nANALOGOUS HISTORICAL CASES (Reference for logic):\n"
        for i, hit in enumerate(analogous, 1):
            few_shot_block += f"Case {i} (Similarity: {hit['score']:.2f}):\nInput: {hit['input'][:200]}...\nOutput: {hit['output'][:200]}...\n---\n"

    instructions = f"""
You are writing the final consumer-facing answer for a local safety assistant.

Use the grounded retrieval result below. Do not invent sources.
{few_shot_block}

Write in Markdown with these sections:
## What I Read
## Likely Product Category
## Potential Chemicals of Concern
## Sources and Regions
## Practical Recommendation
Provide a clear, actionable recommendation based on the grounded evidence and analogous cases.
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
    result = _mlx_generate(model, processor, prompt, None, max_tokens=1000, temperature=0.0)
    if hasattr(result, "text"):
        return result.text.strip()
    return str(result).strip()

def run_native_ocr(image_path: str) -> str:
    try:
        result = subprocess.run(["swift", "native_ocr.swift", image_path], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return result.stdout.strip()
        print(f"Native OCR Error: {result.stderr}")
    except Exception as e:
        print(f"Native OCR failed: {e}")
    return ""

def normalize_image_for_ocr(image_path: str) -> str:
    source = Path(image_path)
    temp_dir = PROJECT_ROOT / "outputs" / "temp_inputs"
    temp_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(str(source.resolve()).encode("utf-8", errors="ignore")).hexdigest()[:10]
    normalized_path = temp_dir / f"{source.stem}_{digest}_normalized.png"

    try:
        with Image.open(source) as img:
            # Respect phone-camera EXIF rotation before OCR/VLM.
            normalized = ImageOps.exif_transpose(img).convert("RGB")
            normalized.save(normalized_path, format="PNG")
        return str(normalized_path)
    except Exception as exc:
        print(f"PIL normalization failed for {source.name}: {exc}")

    # Fallback for formats like HEIC/HEIF that macOS can often decode via sips.
    try:
        result = subprocess.run(
            ["sips", "-s", "format", "png", str(source), "--out", str(normalized_path)],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode == 0 and normalized_path.exists():
            return str(normalized_path)
        print(f"sips conversion failed for {source.name}: {result.stderr.strip()}")
    except Exception as exc:
        print(f"sips conversion failed for {source.name}: {exc}")

    return image_path


def _mlx_generate(model, processor, prompt, image, *, max_tokens: int, temperature: float):
    with _MLX_LOCK:
        return mlx_vlm.generate(model, processor, prompt, image, max_tokens=max_tokens, temperature=temperature)

def run_mlx_ocr(image_path: str) -> str:
    """v1.1 Persona for reliable OCR without tiling."""
    image_path = normalize_image_for_ocr(image_path)
    model, processor = get_model()
    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": ocr_prompt()}]}]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    result = _mlx_generate(model, processor, prompt, image_path, max_tokens=1000, temperature=0.1)
    if hasattr(result, "text"):
        return result.text.strip()
    return str(result).strip()

def prepare_hybrid_ocr_assets(image_path: str, grid=None) -> dict[str, Any]:
    """Helper to run CPU-bound preprocessing in parallel. grid=None for adaptive tiling."""
    normalized_image_path = normalize_image_for_ocr(image_path)
    print(f"Preprocessing assets for {Path(normalized_image_path).name}...")
    raw_native_text = run_native_ocr(normalized_image_path)
    temp_dir = PROJECT_ROOT / "outputs" / "temp_tiles"
    tiles = get_tiles(normalized_image_path, grid=grid, enhance=True)
    tile_paths = save_tiles(tiles, temp_dir, Path(image_path).stem)
    return {
        "image_path": normalized_image_path,
        "native_text": raw_native_text,
        "tile_paths": tile_paths
    }

def run_hybrid_ocr_with_assets(assets: dict[str, Any]) -> str:
    """Sequential MLX portion of Hybrid OCR."""
    image_path = assets["image_path"]
    raw_native_text = assets["native_text"]
    tile_paths = assets["tile_paths"]

    print(f"Running MLX Vision for {Path(image_path).name}...")
    try:
        model, processor = get_model()
        num_tiles = len(tile_paths)

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

        extracted = _mlx_generate(model, processor, prompt, tile_paths, max_tokens=2500, temperature=0.0)
        return extracted.text.strip() if hasattr(extracted, "text") else str(extracted).strip()
    except Exception as e:
        print(f"  MLX Vision failed for {image_path}: {e}")
        return run_mlx_ocr(image_path)

def run_hybrid_ocr(image_path: str, grid=None) -> str:
    """v3.3 Ultimate Hybrid OCR with internal parallel preprocessing. grid=None for adaptive."""
    assets = prepare_hybrid_ocr_assets(image_path, grid=grid)
    return run_hybrid_ocr_with_assets(assets)
def _run_scribe_agent_local(image_paths: list[str], mode: str = "hybrid") -> str:
    """Agent 1: The Scribe - Optimizes M4 by parallelizing preprocessing."""
    valid_paths = [p for p in image_paths if p][:3]
    if not valid_paths: return "No images provided."
        
    if mode == "hybrid":
        print(f"Scribe (v22.0): Parallel Preprocessing + Sequential MLX...")
        
        # 1. Parallel CPU Preprocessing
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(valid_paths)) as executor:
            all_assets = list(executor.map(prepare_hybrid_ocr_assets, valid_paths))
            
        # 2. Sequential GPU Inference
        results = []
        for assets in all_assets:
            results.append(run_hybrid_ocr_with_assets(assets))
            
        return "\n\n".join(results)
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

        title = re.search(r'property="og:title"\s+content="(.*?)"', html, re.I)
        desc = re.search(r'property="og:description"\s+content="(.*?)"', html, re.I)

        title_val = title.group(1) if title else "Unknown Product"
        desc_val = desc.group(1) if desc else ""

        ingredients = ""
        if "sayweee" in domain or "99ranch" in domain:
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

def _run_classifier_agent_local(text: str) -> dict[str, Any]:
    """Agent 2: The Classifier - Proposes category and priority."""
    prompt = structure_prompt(text)
    raw_json = run_mlx_generation(prompt)
    return extract_json_object(raw_json)

def run_search_agent(state_data: dict[str, Any]) -> dict[str, Any]:
    """Agent 3: The Searcher - Performs native and optional semantic retrieval."""
    kb = get_kb()
    store = get_semantic_store()

    product_name = state_data.get("product_name", "Unknown")
    ingredients_text = state_data.get("ingredient_text", "")
    region = state_data.get("region", "California, USA")

    print(f"Forensic Search (Hybrid): {product_name}...")

    # 1. Native Literal Retrieval
    result = kb.retrieve(product_name, ingredients_text, region)

    # 2. Optional Semantic Analogous Retrieval (v21.0)
    result["analogous_cases"] = []
    if store is not None:
        query = f"{product_name} {ingredients_text}"
        analogous_hits = store.search(query, k=2)
        result["analogous_cases"] = [
            {"input": h["sample"]["text"], "output": h["sample"]["output"], "score": float(h["score"])}
            for h in analogous_hits
        ]

    return result

def _run_editor_agent_local(structured_ocr: dict[str, Any], api_result: dict[str, Any]) -> str:
    """Agent 4: The Editor - Synthesizes the final report."""
    prompt = final_answer_prompt(structured_ocr, api_result)
    return run_mlx_generation(prompt)

def _run_feedback_agent_local(user_query: str, context: dict[str, Any]) -> dict[str, Any]:
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

def _run_self_subprocess(command: str, payload: dict[str, Any], *, timeout: int = 240) -> str:
    env = dict(os.environ)
    env["GEMMA4GOOD_CHILD"] = "1"
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), command],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"MLX subprocess failed: {command}")
    return proc.stdout.strip()


def run_classifier_agent(text: str) -> dict[str, Any]:
    if os.getenv("GEMMA4GOOD_CHILD") == "1":
        return _run_classifier_agent_local(text)
    raw = _run_self_subprocess("agent-classify", {"text": text}, timeout=180)
    return extract_json_object(raw)


def run_editor_agent(structured_ocr: dict[str, Any], api_result: dict[str, Any]) -> str:
    if os.getenv("GEMMA4GOOD_CHILD") == "1":
        return _run_editor_agent_local(structured_ocr, api_result)
    return _run_self_subprocess("agent-editor", {"structured_ocr": structured_ocr, "api_result": api_result}, timeout=240)


def run_feedback_agent(user_query: str, context: dict[str, Any]) -> dict[str, Any]:
    if os.getenv("GEMMA4GOOD_CHILD") == "1":
        return _run_feedback_agent_local(user_query, context)
    raw = _run_self_subprocess("agent-feedback", {"user_query": user_query, "context": context}, timeout=180)
    return extract_json_object(raw)


def run_scribe_agent(image_paths: list[str], mode: str = "hybrid") -> str:
    if os.getenv("GEMMA4GOOD_CHILD") == "1":
        return _run_scribe_agent_local(image_paths, mode=mode)
    return _run_self_subprocess("agent-scribe", {"image_paths": image_paths[:3], "mode": mode}, timeout=300)


def verify_category_vlm(category: str, image_paths: list[str]) -> bool:
    if os.getenv("GEMMA4GOOD_CHILD") == "1":
        return _verify_category_vlm_local(category, image_paths)
    raw = _run_self_subprocess("agent-verify-category", {"category": category, "image_paths": image_paths[:3]}, timeout=180)
    return bool(extract_json_object(raw).get("verified", False))


# --- Utility Functions ---

def run_mlx_ocr_multi(image_paths: list[str]) -> str:
    chunks = []
    for idx, path in enumerate(image_paths, start=1):
        if path: chunks.append(f"### Image {idx}\n{run_hybrid_ocr(path)}")
    return "\n\n".join(chunks)

def _verify_category_vlm_local(category: str, image_paths: list[str]) -> bool:
    model, processor = get_model()
    valid_paths = [normalize_image_for_ocr(p) for p in image_paths if p]
    if not valid_paths: return True
    prompt_text = f"Is this product '{category}'? Answer YES or NO."
    messages = [{"role": "user", "content": [{"type": "image"} for _ in range(len(valid_paths))] + [{"type": "text", "text": prompt_text}]}]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    result = _mlx_generate(model, processor, prompt, valid_paths, max_tokens=10, temperature=0.0)
    return "YES" in (result.text.upper() if hasattr(result, "text") else str(result).upper())

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

    subparsers.add_parser("agent-scribe", help="Internal: run OCR agent from stdin JSON")
    subparsers.add_parser("agent-classify", help="Internal: run classify agent from stdin JSON")
    subparsers.add_parser("agent-editor", help="Internal: run editor agent from stdin JSON")
    subparsers.add_parser("agent-feedback", help="Internal: run feedback agent from stdin JSON")
    subparsers.add_parser("agent-verify-category", help="Internal: run category VLM check from stdin JSON")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    if args.command == "test-raw":
        extracted_text = run_hybrid_ocr(args.image) if args.hybrid else run_mlx_ocr_multi([args.image])
        print(f"\n--- Extracted Text ---\n{extracted_text}\n----------------------")

    elif args.command == "test-grounded":
        raw_ocr_text = run_hybrid_ocr(args.image) if args.hybrid else run_mlx_ocr_multi([args.image])
        structured_ocr = _run_classifier_agent_local(raw_ocr_text)
        api_result = run_search_agent({"product_name": structured_ocr.get("product_name"), "ingredient_text": structured_ocr.get("ingredient_text"), "region": args.region})
        final_report = _run_editor_agent_local(structured_ocr, api_result)
        print(f"\n--- Final Report ---\n{final_report}\n--------------------")

    elif args.command == "agent-scribe":
        payload = json.load(sys.stdin)
        print(_run_scribe_agent_local(payload.get("image_paths", []), mode=payload.get("mode", "hybrid")))

    elif args.command == "agent-classify":
        payload = json.load(sys.stdin)
        print(json.dumps(_run_classifier_agent_local(payload.get("text", "")), ensure_ascii=False))

    elif args.command == "agent-editor":
        payload = json.load(sys.stdin)
        print(_run_editor_agent_local(payload.get("structured_ocr", {}), payload.get("api_result", {})))

    elif args.command == "agent-feedback":
        payload = json.load(sys.stdin)
        print(json.dumps(_run_feedback_agent_local(payload.get("user_query", ""), payload.get("context", {})), ensure_ascii=False))

    elif args.command == "agent-verify-category":
        payload = json.load(sys.stdin)
        print(json.dumps({"verified": _verify_category_vlm_local(payload.get("category", "unknown"), payload.get("image_paths", []))}, ensure_ascii=False))

if __name__ == "__main__":
    main()
