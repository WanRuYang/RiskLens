import base64
import copy
import json
import os
import re
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import gradio as gr

from platform_profiles import MAC_DEV, PIXEL8_ANDROID

from app_shared import build_envelope, call_local_api, check_local_api, dump_debug_json
from prompt_utils import format_prompt


OPENAI_MODEL = os.getenv("GEMMA4GOOD_OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_KEY_PATH = Path.home() / ".ssh" / "openai_api_key.txt"


def api_result_for_final_prompt(api_result: dict[str, Any]) -> dict[str, Any]:
    prompt_result = copy.deepcopy(api_result)
    scope = prompt_result.get("evidence_scope_summary") or {}
    if not scope.get("has_direct_chemical_match") and not scope.get("has_direct_regulatory_evidence"):
        linkage_lists = [prompt_result.get("candidate_chemical_linkages", []) or []]
        product_label_model = prompt_result.get("product_label_model") or {}
        if isinstance(product_label_model, dict):
            linkage_lists.append(product_label_model.get("candidate_chemical_linkages", []) or [])
        for row in [item for rows in linkage_lists for item in rows]:
            row["top_chemicals"] = []
            row["example_products"] = []
            row["prompt_note"] = (
                "Hypothesis-only pathway. Do not name specific chemicals for this product unless there is a direct label, "
                "ingredient, material, warning, or regulatory match."
            )
    return prompt_result


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
- material_text
- processing_method
- packaging_material
- processing_derivatives
- concentration_assessment
- warning_text
- safety_caution_text
- category_clues
- confidence_notes

Rules:
- Put label or front-of-pack product naming into product_name.
- For food and household cleaners, prioritize the explicit ingredient list in ingredient_text. If ingredients are missing, leave ingredient_text empty and explain the missing field in confidence_notes.
- For non-food/non-cleaner products, put what the item is made of into material_text, such as PVC, soft plastic, stainless steel, non-stick coating, textile, leather, composite wood, or unknown.
- Put packaging/contact clues into packaging_material, such as plastic bottle, wrapper, can lining, grease-resistant bag, microwave popcorn bag, or food container.
- Put product/process clues into processing_method, such as baked, fried, roasted, smoked, cured, grilled, refined oil, frozen, raw, or unknown. A cookie/cracker is normally baked; chips/fries are normally fried unless text says otherwise; coffee is roasted; plain fresh/raw meat should stay raw/minimally processed.
- Put possible process-derived compounds into processing_derivatives only when the process clue supports them, such as acrylamide for baked/fried/roasted foods, glycidyl esters/3-MCPD for refined oils, PAHs/nitrosamines for smoked/cured/grilled meat.
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

Evidence rules:
- Treat chemical_matches, direct_regulatory_evidence, and concern_sources as product-specific evidence.
- Treat category_level_regulatory_evidence, category_level_concern_sources, and candidate_chemical_linkages as context or hypotheses only.
- If there is no direct chemical match, do not say the product "contains" or "has" those chemicals.
- For foods, separate listed ingredients from processing/container hypotheses. Say "possible exposure pathways to consider" only when evidence is category-level.
- Do not treat "surfactant" as automatically hazardous. For surfactants, distinguish specific ingredient/family concerns: ethoxylated surfactants may indicate possible 1,4-dioxane residual contamination; alkylphenol ethoxylates are environmental/endocrine concerns; SLS/CAPB/quats are mainly irritation or sensitization concerns unless a specific carcinogenic contaminant is detected.
- If food_processing_profile.processing_level is minimally_processed_raw_meat, do not infer additives, PAHs, nitrosamines, acrylamide, or Prop 65 chemicals from broad food-category patterns. Say the current evidence looks limited to plain meat unless an ingredient/warning label says otherwise.
- If structured_risk_output.product_summary.ingredient_material_status says ingredient/material is unknown, state that plainly and frame the analysis as an inference from product name and category rather than a label-confirmed ingredient/material review.
- If the item is not on Prop 65 or no Prop 65 label/direct match is found, say that clearly.

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
            json.dumps(api_result_for_final_prompt(api_result), ensure_ascii=False, indent=2, default=str),
        ]
    )
    return format_prompt(
        task_name="Write final grounded answer",
        instructions=instructions,
        payload=payload,
        include_category_reference=True,
    )


def analyze_product(
    images: list[str],
    user_id: str,
    region_label: str,
    product_page_url: str,
    direct_text: str,
    queue_for_review: bool,
    review_notes: str,
) -> tuple[str, str]:
    if not images and not direct_text.strip():
        return "請先上傳 1 到 3 張圖片，或直接貼上產品文字 / ingredient / warning 內容。", "{}"

    healthy, detail = check_local_api()
    if not healthy:
        return (
            f"本地 API 目前無法連線：{detail}\n\n請先在 repo 的 database 目錄啟動：`cd /Users/adelie/Projects/gemma4good/database && ../.venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8010`",
            "{}",
        )

    try:
        api_key = load_openai_api_key()
    except Exception as exc:
        return f"OpenAI API key 載入失敗：{exc}", "{}"

    ocr_chunks: list[str] = []
    for idx, image_path in enumerate((images or [])[:3], start=1):
        content = [
            {"type": "input_text", "text": ocr_prompt(idx)},
            {"type": "input_image", "image_url": image_to_data_url(image_path), "detail": "high"},
        ]
        extracted = call_openai_responses_api(api_key=api_key, model=OPENAI_MODEL, content=content)
        ocr_chunks.append(f"### Image {idx}\n{extracted}")
    if direct_text.strip():
        ocr_chunks.append(f"### Direct Text Input\n{direct_text.strip()}")

    raw_ocr_text = "\n\n".join(ocr_chunks).strip()
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
    structured_ocr["confidence_notes"] = " | ".join(
        part
        for part in [
            structured_ocr.get("confidence_notes", ""),
            "contains_direct_text_input" if direct_text.strip() else "",
            "contains_product_page_url" if product_page_url.strip() else "",
        ]
        if part
    )

    envelope = build_envelope(
        user_id=user_id.strip() or "openai_demo_user",
        region=region_label.strip() or "California, USA",
        product_page_url=product_page_url.strip(),
        raw_ocr_text=raw_ocr_text,
        structured_data=structured_ocr,
        input_mode="text" if direct_text.strip() and not images else "image",
        user_question="",
        user_corrected_text=bool(direct_text.strip()),
        user_corrected_category=False,
        queue_for_review=queue_for_review,
        review_notes=review_notes,
    )
    api_result = call_local_api(envelope.as_api_payload())

    final_report = call_openai_responses_api(
        api_key=api_key,
        model=OPENAI_MODEL,
        content=[{"type": "input_text", "text": final_answer_prompt(structured_ocr, api_result)}],
    )

    debug_json = dump_debug_json(
        envelope=envelope,
        structured_data=structured_ocr,
        api_result={**api_result, "openai_model": OPENAI_MODEL},
        provider="openai_reference",
        raw_ocr_text=raw_ocr_text,
    )
    return final_report, debug_json


with gr.Blocks(theme=gr.themes.Soft(), title="gemma4good-openai") as demo:
    gr.Markdown("# gemma4good (OpenAI reference + local risk DB)")
    gr.Markdown(
        f"Current shell: **{MAC_DEV.name}**. Portable target: **{PIXEL8_ANDROID.name}**. OpenAI remains evaluation-only.\n\nUpload 1 to 3 images of a product label, ingredients panel, or Prop 65 warning. "
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
            direct_text = gr.Textbox(
                label="Optional direct text input",
                lines=8,
                placeholder="Paste product title, ingredients, warning text, or cleaning-safety instructions here...",
            )
            input_files = gr.File(file_count="multiple", file_types=["image"], label="Upload 1-3 images")
            queue_for_review = gr.Checkbox(label="Queue this case for review", value=False)
            review_notes = gr.Textbox(label="Optional review notes", lines=2)
            analyze_btn = gr.Button("Analyze Product", variant="primary")
        with gr.Column(scale=2):
            final_report = gr.Markdown(label="Final Answer")
            debug_json = gr.Code(label="Debug JSON", language="json")

    analyze_btn.click(
        fn=analyze_product,
        inputs=[input_files, user_id, region, product_link, direct_text, queue_for_review, review_notes],
        outputs=[final_report, debug_json],
    )

    gr.HTML(
        """
        <div style="margin-top: 20px; padding: 15px; background: #f0f4f8; border-radius: 8px;">
            <p><b>Flow:</b> OpenAI OCR/structuring or direct text -> local API -> OpenAI final answer</p>
            <ul>
                <li>Image 1 can be the product front or product type.</li>
                <li>Image 2 can be the ingredients panel.</li>
                <li>Image 3 can be the Prop 65 or other warning text.</li>
                <li>You can also skip images and paste text directly for Stage 2 testing.</li>
                <li>An optional product page link can provide product-title or category clues, but it is not treated as proof of the full ingredient list.</li>
                <li>If a cleaner says to use gloves, a mask, or ventilation, that should be captured as a usage-safety caution.</li>
            </ul>
        </div>
        """
    )


if __name__ == "__main__":
    demo.launch()
