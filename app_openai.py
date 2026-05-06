import base64
import json
import os
import re
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import gradio as gr
import requests

from prompt_utils import format_prompt


API_BASE_URL = os.getenv("GEMMA4GOOD_API_BASE_URL", "http://127.0.0.1:8010")
OPENAI_MODEL = os.getenv("GEMMA4GOOD_OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_KEY_PATH = Path.home() / ".ssh" / "openai_api_key.txt"


def load_openai_api_key(path: Path = OPENAI_KEY_PATH) -> str:
    key = path.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError(f"OpenAI API key file is empty: {path}")
    return key


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {}


def image_to_data_url(path: str) -> str:
    image_path = Path(path)
    suffix = image_path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def call_openai_responses_api(
    *,
    api_key: str,
    model: str,
    content: list[dict[str, Any]],
) -> str:
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": content,
            }
        ],
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {error_body}") from exc

    data = json.loads(body)
    output_text = data.get("output_text", "")
    if not output_text:
        parts = []
        for item in data.get("output", []):
            for piece in item.get("content", []):
                if piece.get("type") == "output_text":
                    parts.append(piece.get("text", ""))
        output_text = "\n".join(part for part in parts if part)
    return output_text.strip()


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
        api_key = load_openai_api_key()
    except Exception as exc:
        return f"OpenAI API key 載入失敗：{exc}", "{}"

    ocr_chunks: list[str] = []
    for idx, image_path in enumerate(images[:3], start=1):
        content = [
            {"type": "input_text", "text": ocr_prompt(idx)},
            {"type": "input_image", "image_url": image_to_data_url(image_path), "detail": "high"},
        ]
        extracted = call_openai_responses_api(api_key=api_key, model=OPENAI_MODEL, content=content)
        ocr_chunks.append(f"### Image {idx}\n{extracted}")

    raw_ocr_text = "\n\n".join(ocr_chunks)
    structured_text = call_openai_responses_api(
        api_key=api_key,
        model=OPENAI_MODEL,
        content=[{"type": "input_text", "text": structure_prompt(raw_ocr_text)}],
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
        "user_id": user_id.strip() or "openai_demo_user",
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

    final_report = call_openai_responses_api(
        api_key=api_key,
        model=OPENAI_MODEL,
        content=[{"type": "input_text", "text": final_answer_prompt(structured_ocr, api_result)}],
    )

    debug_payload = {
        "raw_ocr_text": raw_ocr_text,
        "structured_ocr": structured_ocr,
        "api_result": api_result,
        "openai_model": OPENAI_MODEL,
    }
    return final_report, json.dumps(debug_payload, ensure_ascii=False, indent=2)


with gr.Blocks(theme=gr.themes.Soft(), title="gemma4good-openai") as demo:
    gr.Markdown("# gemma4good (OpenAI + local risk DB)")
    gr.Markdown(
        "Upload 1 to 3 images of a product label, ingredients panel, or Prop 65 warning. "
        "You can also provide an optional product page link. "
        "OpenAI will extract and structure the text, the local API will retrieve grounded evidence, and OpenAI will produce the final explanation."
    )

    with gr.Row():
        with gr.Column(scale=1):
            user_id = gr.Textbox(label="User ID", value="openai_demo_user")
            region = gr.Textbox(label="Region", value="California, USA")
            product_link = gr.Textbox(
                label="Optional product page link",
                placeholder="https://www.amazon.com/... or https://www.sayweee.com/...",
            )
            input_files = gr.File(file_count="multiple", file_types=["image"], label="Upload 1-3 images")
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
            <p><b>Flow:</b> OpenAI OCR/structuring -> local API -> OpenAI final answer</p>
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
