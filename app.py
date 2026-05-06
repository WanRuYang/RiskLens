import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import gradio as gr
import kagglehub
import requests
import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor

from prompt_utils import extract_json_object, format_prompt

API_BASE_URL = os.getenv("GEMMA4GOOD_API_BASE_URL", "http://127.0.0.1:8010")
VARIATION = "gemma-4-e4b-it"
MODEL_HANDLE = f"google/gemma-4/transformers/{VARIATION}"
_MODEL_CACHE: tuple[AutoProcessor, AutoModelForCausalLM] | None = None
PROJECT_ROOT = Path(__file__).resolve().parent


def load_kaggle_credentials() -> bool:
    kaggle_dir = Path.home() / ".kaggle"
    user_file = kaggle_dir / "user_name"
    token_file = kaggle_dir / "access_token"
    if not user_file.exists() or not token_file.exists():
        return False
    os.environ["KAGGLE_USERNAME"] = user_file.read_text().strip()
    os.environ["KAGGLE_KEY"] = token_file.read_text().strip()
    return True


def generate_with_model(
    processor: AutoProcessor,
    model: AutoModelForCausalLM,
    *,
    text_prompt: str,
    image: Image.Image | None = None,
    max_new_tokens: int = 500,
) -> str:
    content: list[dict[str, Any]] = []
    if image is not None:
        content.append({"type": "image", "image": image})
    content.append({"type": "text", "text": text_prompt})
    messages = [{"role": "user", "content": content}]
    prompt_str = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    kwargs: dict[str, Any] = {"text": prompt_str, "return_tensors": "pt"}
    if image is not None:
        kwargs["images"] = image
    inputs = processor(**kwargs).to(model.device)
    with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    return processor.decode(output[0][inputs.input_ids.shape[-1] :], skip_special_tokens=True).strip()


def get_model() -> tuple[AutoProcessor, AutoModelForCausalLM]:
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE
    if not load_kaggle_credentials():
        raise RuntimeError("Kaggle credentials not found.")
    print(f"Loading model {VARIATION}...")
    model_path = kagglehub.model_download(MODEL_HANDLE)
    processor = AutoProcessor.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    _MODEL_CACHE = (processor, model)
    return _MODEL_CACHE


def ocr_prompt(image_index: int) -> str:
    instructions = f"""
Extract visible text from image {image_index} as faithfully as possible.

Focus on:
- product name
- ingredients
- warning text
- Proposition 65 text
- use instructions
- safety instructions
- caution statements
- protective gear guidance such as gloves, mask, eye protection, or ventilation

Return plain text only.
Do not summarize.
Preserve line breaks when useful.
"""
    return format_prompt(task_name=f"OCR image {image_index}", instructions=instructions)


def structure_prompt(raw_text: str) -> str:
    instructions = """
You are structuring OCR output from one to three product images.

Return ONLY valid JSON with these keys:
- product_name
- ingredient_text
- warning_text
- safety_caution_text
- category_clues
- confidence_notes

Rules:
- Put label or front-of-pack product naming into product_name.
- Put ingredients or materials into ingredient_text.
- Put Prop 65 or formal warning labels into warning_text.
- Put instructions such as use gloves, use mask, ventilation, avoid inhalation, keep away from children into safety_caution_text.
- Put material or usage hints into category_clues.
- If the product looks like food or a household cleaner, prioritize ingredient details in ingredient_text.
- If the product looks like another category, prioritize material or construction clues in category_clues.
- If a field is not visible, use an empty string.
"""
    return format_prompt(
        task_name="Structure OCR output",
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


def load_images(file_paths: list[str]) -> list[Image.Image]:
    images: list[Image.Image] = []
    for path in file_paths[:3]:
        images.append(Image.open(path).convert("RGB"))
    return images


def call_local_api(payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(f"{API_BASE_URL}/analyze-product", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def analyze_product(images: list[str], user_id: str, region_label: str, product_page_url: str) -> tuple[str, str]:
    if not images:
        return "請先上傳 1 到 3 張圖片。", "{}"

    try:
        health = requests.get(f"{API_BASE_URL}/health", timeout=5)
        health.raise_for_status()
    except Exception as exc:
        return (
            f"本地 API 目前無法連線：{exc}\n\n請先在 database 目錄啟動：`python3 -m uvicorn api:app --host 127.0.0.1 --port 8010`",
            "{}",
        )

    try:
        processor, model = get_model()
    except Exception as exc:
        return f"Gemma 4 模型載入失敗：{exc}", "{}"

    pil_images = load_images(images)
    ocr_chunks: list[str] = []
    for idx, image in enumerate(pil_images, start=1):
        extracted = generate_with_model(
            processor,
            model,
            text_prompt=ocr_prompt(idx),
            image=image,
            max_new_tokens=350,
        )
        ocr_chunks.append(f"### Image {idx}\n{extracted}")

    raw_ocr_text = "\n\n".join(ocr_chunks)
    structured_text = generate_with_model(
        processor,
        model,
        text_prompt=structure_prompt(raw_ocr_text),
        image=None,
        max_new_tokens=260,
    )
    structured_ocr = extract_json_object(structured_text)
    if not structured_ocr:
        structured_ocr = {
            "product_name": "",
            "ingredient_text": raw_ocr_text,
            "warning_text": "",
            "safety_caution_text": "",
            "category_clues": "",
            "confidence_notes": "Structured OCR parsing failed; using raw OCR text fallback.",
        }
    structured_ocr["product_page_url"] = product_page_url.strip()

    payload = {
        "user_id": user_id.strip() or "local_demo_user",
        "session_id": str(uuid.uuid4()),
        "product_name": structured_ocr.get("product_name") or "",
        "product_page_url": product_page_url.strip(),
        "raw_ocr_text": raw_ocr_text,
        "ingredients_text": " | ".join(
            part
            for part in [
                structured_ocr.get("ingredient_text", ""),
                structured_ocr.get("category_clues", ""),
            ]
            if part
        ),
        "warning_text": " | ".join(
            part
            for part in [
                structured_ocr.get("warning_text", ""),
                structured_ocr.get("safety_caution_text", ""),
            ]
            if part
        ),
        "region": region_label.strip() or "California, USA",
        "save_to_history": True,
    }
    api_result = call_local_api(payload)

    final_report = generate_with_model(
        processor,
        model,
        text_prompt=final_answer_prompt(structured_ocr, api_result),
        image=None,
        max_new_tokens=800,
    )

    debug_payload = {
        "raw_ocr_text": raw_ocr_text,
        "structured_ocr": structured_ocr,
        "api_result": api_result,
    }
    return final_report, json.dumps(debug_payload, ensure_ascii=False, indent=2)


with gr.Blocks(theme=gr.themes.Soft(), title="gemma4good") as demo:
    gr.Markdown("# gemma4good")
    gr.Markdown(
        "Upload 1 to 3 images of a product label, ingredients panel, or Prop 65 warning. "
        "You can also provide an optional product page link. "
        "Gemma 4 will extract the text, the local API will retrieve grounded evidence, and Gemma 4 will produce the final explanation."
    )

    with gr.Row():
        with gr.Column(scale=1):
            user_id = gr.Textbox(label="User ID", value="local_demo_user")
            region = gr.Textbox(label="Region", value="California, USA")
            product_link = gr.Textbox(
                label="Optional product page link",
                placeholder="https://www.amazon.com/... or https://www.sayweee.com/...",
            )
            input_files = gr.File(
                file_count="multiple",
                file_types=["image"],
                label="Upload 1-3 images",
            )
            analyze_btn = gr.Button("Analyze Product", variant="primary")
        with gr.Column(scale=2):
            final_report = gr.Markdown(label="Final Answer")
            debug_json = gr.Code(label="Debug JSON", language="json")

    analyze_btn.click(
        fn=analyze_product,
        inputs=[input_files, user_id, region, product_link],
        outputs=[final_report, debug_json],
    )

    gr.HTML(
        """
        <div style="margin-top: 20px; padding: 15px; background: #f0f4f8; border-radius: 8px;">
            <p><b>Flow:</b> Gemma OCR -> local API -> final answer</p>
            <ul>
                <li>Image 1 can be the product front or product type.</li>
                <li>Image 2 can be the ingredients panel.</li>
                <li>Image 3 can be the Prop 65 or other warning text.</li>
                <li>An optional product page link can provide product-title or category clues, but it is not treated as proof of the full ingredient list.</li>
                <li>If a cleaner says to use gloves, a mask, or ventilation, that should be captured as a usage-safety caution.</li>
            </ul>
        </div>
        """
    )


if __name__ == "__main__":
    demo.launch()
