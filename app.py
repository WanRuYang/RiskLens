from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import gradio as gr

from app_shared import build_envelope, call_local_api, check_local_api, dump_debug_json, preview_url
from mlx_engine import (
    run_classifier_agent,
    run_editor_agent,
    run_feedback_agent,
    run_scribe_agent,
    verify_category_vlm,
)
from platform_profiles import MAC_DEV, PIXEL8_ANDROID


INPUT_MODES = {
    "image": "Image(s) + product description",
    "url": "Product URL",
    "text": "Type product name / description",
}


@dataclass
class SessionState:
    user_id: str = "local_demo_user"
    region: str = "California, USA"
    current_state: str = "INIT"
    input_mode: str = "image"
    raw_ocr_text: str = ""
    confirmed_text: str = ""
    proposed_category: dict[str, Any] = field(default_factory=dict)
    confirmed_category: dict[str, Any] = field(default_factory=dict)
    api_result: dict[str, Any] = field(default_factory=dict)
    final_report: str = ""
    image_paths: list[str] = field(default_factory=list)
    product_link: str = ""
    direct_text: str = ""
    queue_for_review: bool = False
    review_notes: str = ""
    user_corrected_text: bool = False
    user_corrected_category: bool = False
    latest_vlm_check: str = "N/A"
    url_preview: dict[str, Any] = field(default_factory=dict)


def _safe_text(value: str | None) -> str:
    return value.strip() if isinstance(value, str) else ""


def _join_sections(sections: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    for label, value in sections:
        clean = _safe_text(value)
        if clean:
            parts.append(f"### {label}\n{clean}")
    return "\n\n".join(parts).strip()


def _looks_sparse(text: str, *, threshold: int = 20) -> bool:
    return len(_safe_text(text)) < threshold


def _mode_specific_guidance(mode: str) -> str:
    if mode == "image":
        return (
            "Upload 1 to 3 clearer images and optionally include a short product description. "
            "If the label is still hard to read, switch to URL or typed text."
        )
    if mode == "url":
        return "Re-enter the product URL. If the page still cannot be read, switch to images or typed text."
    return "Add more product detail, ingredients, or warning text. If the text is still incomplete, switch to a product URL or images."


def _format_url_preview(preview: dict[str, Any]) -> str:
    url_context = preview.get("url_context", {})
    assessment = preview.get("intake_assessment", {})
    parts = [
        f"Status: {assessment.get('status', 'unknown')}",
        f"Can proceed: {assessment.get('can_proceed', False)}",
        f"Reason: {assessment.get('reason', '')}",
        f"Recommended next step: {assessment.get('recommended_next_step', '')}",
    ]
    body = _join_sections([
        ("Fetched Product Text", url_context.get("product_text", "")),
        ("Fetched Ingredients", url_context.get("ingredients_text", "")),
        ("Fetched Warnings", url_context.get("warning_text", "")),
        ("Fetch Error", url_context.get("fetch_error", "")),
    ])
    if body:
        parts.append("")
        parts.append(body)
    return "\n".join(parts).strip()


def preview_url_for_ui(product_link: str, region: str) -> str:
    healthy, detail = check_local_api()
    if not healthy:
        return f"Local API unavailable: {detail}"
    link = _safe_text(product_link)
    if not link:
        return "Enter a product URL first."
    try:
        preview = preview_url(link, region or "California, USA")
    except Exception as exc:  # pragma: no cover
        return f"URL preview failed: {exc}"
    return _format_url_preview(preview)


def build_search_envelope(state: SessionState, *, ingredient_override: str = ""):
    structured = dict(state.confirmed_category)
    if ingredient_override:
        structured["ingredient_text"] = ingredient_override
    structured.setdefault("category_clues", structured.get("reasoning", ""))
    structured.setdefault("confidence_notes", state.latest_vlm_check)
    return build_envelope(
        user_id=state.user_id,
        region=state.region,
        product_page_url=state.product_link,
        raw_ocr_text=state.confirmed_text or state.raw_ocr_text,
        structured_data=structured,
        input_mode=state.input_mode,
        user_corrected_text=state.user_corrected_text,
        user_corrected_category=state.user_corrected_category,
        queue_for_review=state.queue_for_review or state.user_corrected_text or state.user_corrected_category,
        review_notes=state.review_notes,
    )


def run_grounded_search(state: SessionState, *, ingredient_override: str = "") -> dict[str, Any]:
    envelope = build_search_envelope(state, ingredient_override=ingredient_override)
    return call_local_api(envelope.as_api_payload())


def collect_mode_input(state: SessionState) -> tuple[bool, str]:
    mode = state.input_mode
    sections: list[tuple[str, str]] = []

    if mode == "image":
        if not state.image_paths:
            return False, "Image mode needs 1 to 3 product images."
        ocr_text = run_scribe_agent(state.image_paths)
        if _looks_sparse(ocr_text, threshold=15):
            return False, "I could not read enough text from the images. Please upload clearer images or try the product URL / typed text path."
        sections.append(("OCR From Images", ocr_text))
        if state.direct_text:
            sections.append(("Product Description", state.direct_text))
        state.raw_ocr_text = _join_sections(sections)
        return True, state.raw_ocr_text

    if mode == "url":
        if not state.product_link:
            return False, "URL mode needs a product page link."
        preview = preview_url(state.product_link, state.region)
        state.url_preview = preview
        assessment = preview.get("intake_assessment", {})
        if not assessment.get("can_proceed", True):
            return False, assessment.get("reason", "I could not read enough from the product page.")
        url_context = preview.get("url_context", {})
        sections.extend([
            ("Product Page Title / Description", url_context.get("product_text", "")),
            ("Ingredients From Page", url_context.get("ingredients_text", "")),
            ("Warnings From Page", url_context.get("warning_text", "")),
        ])
        state.raw_ocr_text = _join_sections(sections)
        return True, state.raw_ocr_text

    if not state.direct_text:
        return False, "Text mode needs a typed product name or description."
    if _looks_sparse(state.direct_text, threshold=25):
        return False, "The typed description is still too short to analyze reliably. Please add more detail, or try URL / image mode."
    sections.append(("Direct Text Input", state.direct_text))
    state.raw_ocr_text = _join_sections(sections)
    return True, state.raw_ocr_text


def analyze_product(
    images: list[str],
    user_id: str,
    region_label: str,
    product_page_url: str,
    direct_text: str = "",
    queue_for_review: bool = False,
    review_notes: str = "",
    input_mode: str = "image",
) -> tuple[str, str]:
    healthy, detail = check_local_api()
    if not healthy:
        return (
            f"本地 API 目前無法連線：{detail}\n\n請先在 database 目錄啟動：`python3 -m uvicorn api:app --host 127.0.0.1 --port 8010`",
            "{}",
        )

    state = SessionState(
        user_id=user_id or "local_demo_user",
        region=region_label or "California, USA",
        input_mode=input_mode,
        image_paths=[path for path in images[:3] if path],
        product_link=_safe_text(product_page_url),
        direct_text=_safe_text(direct_text),
        queue_for_review=queue_for_review,
        review_notes=review_notes,
    )
    ok, intake_text = collect_mode_input(state)
    if not ok:
        return f"Input needs improvement: {intake_text}\n\n{_mode_specific_guidance(state.input_mode)}", "{}"

    state.confirmed_text = intake_text
    structured = run_classifier_agent(state.confirmed_text)
    if state.image_paths:
        try:
            vlm_check = (
                "PASSED ✅"
                if verify_category_vlm(structured.get("product_use_category", "unknown"), state.image_paths)
                else "CAUTION ⚠️ (visual drift detected)"
            )
        except Exception as exc:  # pragma: no cover
            vlm_check = f"UNAVAILABLE ({exc})"
    else:
        vlm_check = "N/A"

    structured["confidence_notes"] = vlm_check
    envelope = build_envelope(
        user_id=state.user_id,
        region=state.region,
        product_page_url=state.product_link,
        raw_ocr_text=state.confirmed_text,
        structured_data=structured,
        input_mode=state.input_mode,
        user_corrected_text=bool(state.direct_text and state.image_paths),
        user_corrected_category=False,
        queue_for_review=queue_for_review,
        review_notes=review_notes,
    )
    api_result = call_local_api(envelope.as_api_payload())
    intake_assessment = api_result.get("intake_assessment", {})
    if not intake_assessment.get("can_proceed", True):
        return (
            f"Input needs improvement: {intake_assessment.get('reason', 'The current input was not sufficient.')}\n\n"
            f"Recommended next step: {intake_assessment.get('recommended_next_step', 'try another input method')}",
            dump_debug_json(
                envelope=envelope,
                structured_data=structured,
                api_result=api_result,
                provider="gemma_product",
                raw_ocr_text=state.confirmed_text,
            ),
        )
    final_report = run_editor_agent({**structured, "product_page_url": product_page_url}, api_result)
    debug_json = dump_debug_json(
        envelope=envelope,
        structured_data=structured,
        api_result=api_result,
        provider="gemma_product",
        raw_ocr_text=state.confirmed_text,
    )
    return final_report, debug_json


def process_chat(
    message: str,
    history: list[tuple[str, str]],
    state: SessionState | None,
    user_id_val: str,
    region_val: str,
    input_mode_val: str,
    product_link_val: str,
    direct_text_val: str,
    queue_for_review_val: bool,
    review_notes_val: str,
    image_files,
):
    message = message or ""
    if state is None:
        state = SessionState()

    state.user_id = _safe_text(user_id_val) or state.user_id
    state.region = _safe_text(region_val) or state.region
    state.input_mode = input_mode_val or state.input_mode
    state.product_link = _safe_text(product_link_val)
    state.direct_text = _safe_text(direct_text_val)
    state.queue_for_review = bool(queue_for_review_val)
    state.review_notes = _safe_text(review_notes_val)
    state.image_paths = [f.name for f in image_files] if image_files else []

    if state.current_state == "INIT":
        ok, intake_text = collect_mode_input(state)
        if not ok:
            return (
                f"I need better input for **{INPUT_MODES.get(state.input_mode, state.input_mode)}**.\n\n"
                f"Reason: {intake_text}\n\n"
                f"Next step: {_mode_specific_guidance(state.input_mode)}",
                state,
            )

        state.current_state = "AWAITING_TEXT_CONFIRM"
        return (
            "I collected the first-pass product text for the selected mode. Please confirm it before we classify and search.\n\n"
            f"**Extracted / Combined Text:**\n{intake_text}\n\n"
            "Reply `yes` if this looks right, or paste a corrected version.",
            state,
        )

    if state.current_state == "AWAITING_TEXT_CONFIRM":
        if _safe_text(message).lower() in {"yes", "y", "correct", "ok"}:
            state.confirmed_text = state.raw_ocr_text
            state.user_corrected_text = False
        else:
            state.confirmed_text = _safe_text(message)
            state.user_corrected_text = True

        if state.input_mode == "text" and _looks_sparse(state.confirmed_text, threshold=25):
            state.current_state = "INIT"
            return (
                "The typed text is still too incomplete for a grounded answer. Please add more product detail, or switch to URL / image mode.",
                state,
            )

        proposed = run_classifier_agent(state.confirmed_text)
        state.proposed_category = proposed
        state.current_state = "AWAITING_CAT_CONFIRM"
        state.latest_vlm_check = "N/A"

        if state.input_mode == "image" and state.image_paths:
            try:
                verified = verify_category_vlm(proposed.get("product_use_category", "unknown"), state.image_paths)
                state.latest_vlm_check = "PASSED ✅" if verified else "CAUTION ⚠️ (visual drift detected)"
            except Exception as exc:  # pragma: no cover
                state.latest_vlm_check = f"UNAVAILABLE ({exc})"

        return (
            "I finished the first-pass category/material alignment.\n\n"
            f"- Category: **{proposed.get('product_use_category', 'unknown')}**\n"
            f"- Material/Form: **{proposed.get('material_or_form', 'unknown')}**\n"
            f"- Priority: **{proposed.get('information_priority', 'material_first')}**\n"
            f"- Self-check: **{state.latest_vlm_check}**\n"
            f"- Reasoning: *{proposed.get('reasoning', 'No reasoning provided')}*\n\n"
            "Reply `yes` if this is acceptable, or type a corrected category.",
            state,
        )

    if state.current_state == "AWAITING_CAT_CONFIRM":
        if _safe_text(message).lower() in {"yes", "y", "correct", "ok"}:
            state.confirmed_category = dict(state.proposed_category)
            state.user_corrected_category = False
        else:
            state.confirmed_category = dict(state.proposed_category)
            state.confirmed_category["product_use_category"] = _safe_text(message) or state.proposed_category.get(
                "product_use_category", "unknown"
            )
            state.user_corrected_category = True

        healthy, detail = check_local_api()
        if not healthy:
            return (
                f"The local API is not reachable: {detail}\n\nStart it first with `python3 -m uvicorn api:app --host 127.0.0.1 --port 8010`.",
                state,
            )

        state.api_result = run_grounded_search(state)
        intake_assessment = state.api_result.get("intake_assessment", {})
        if not intake_assessment.get("can_proceed", True):
            state.current_state = "INIT"
            return (
                "The system still thinks the current input is not strong enough for a grounded answer.\n\n"
                f"Reason: {intake_assessment.get('reason', 'input not sufficient')}\n\n"
                f"Recommended next step: {intake_assessment.get('recommended_next_step', 'try another method')}",
                state,
            )

        state.final_report = run_editor_agent(
            {
                **state.confirmed_category,
                "product_page_url": state.product_link,
                "confidence_notes": state.latest_vlm_check,
            },
            state.api_result,
        )
        state.current_state = "FEEDBACK"
        return (
            f"### Final Safety Analysis\n\n{state.final_report}\n\n---\nYou can now ask follow-up questions, add better images, or rerun with a different region or ingredient clue.",
            state,
        )

    if state.current_state == "FEEDBACK":
        action = "NONE"
        feedback_result: dict[str, Any] = {}

        if state.input_mode == "image" and image_files:
            new_paths = [f.name for f in image_files]
            if len(new_paths) > len(state.image_paths):
                added_images = [path for path in new_paths if path not in state.image_paths]
                state.image_paths = new_paths
                supplemental = run_scribe_agent(added_images)
                if _looks_sparse(supplemental, threshold=15):
                    return (
                        "The new images still did not produce enough text. Please try clearer images or switch to URL / text mode.",
                        state,
                    )
                state.confirmed_text = _join_sections([
                    ("Confirmed Text", state.confirmed_text),
                    ("Supplemental OCR", supplemental),
                ])
                state.user_corrected_text = True
                return (
                    "I received the new images and added the supplemental OCR text. Reply `rerun` to search again with this updated input.",
                    state,
                )

        if _safe_text(message).lower() == "rerun":
            action = "RERUN_SEARCH"
            feedback_result = {"action_payload": {}}
            bot_message = "Understood. I will rerun the grounded search with the current text."
        else:
            feedback_result = run_feedback_agent(message, {"api_result": state.api_result, "report": state.final_report})
            bot_message = feedback_result.get(
                "response",
                "I can help rerun with a different region, ingredient clue, or updated input method.",
            )
            action = feedback_result.get("action", "NONE")

        if action == "RERUN_SEARCH":
            payload = feedback_result.get("action_payload", {})
            state.region = payload.get("region", state.region) or state.region
            ingredient_override = payload.get("ingredients", state.confirmed_category.get("ingredient_text", ""))
            state.api_result = run_grounded_search(state, ingredient_override=ingredient_override)
            intake_assessment = state.api_result.get("intake_assessment", {})
            if not intake_assessment.get("can_proceed", True):
                state.current_state = "INIT"
                return (
                    f"{bot_message}\n\nThe rerun still needs better input. {intake_assessment.get('reason', '')}\n\n"
                    f"Recommended next step: {intake_assessment.get('recommended_next_step', 'try another method')}",
                    state,
                )
            state.final_report = run_editor_agent(
                {
                    **state.confirmed_category,
                    "ingredient_text": ingredient_override or state.confirmed_category.get("ingredient_text", ""),
                    "product_page_url": state.product_link,
                    "confidence_notes": state.latest_vlm_check,
                },
                state.api_result,
            )
            bot_message += f"\n\n### Updated Safety Analysis\n\n{state.final_report}"
        elif action == "UPDATE_CATEGORY":
            payload = feedback_result.get("action_payload", {})
            new_category = payload.get("category", "unknown")
            state.confirmed_category["product_use_category"] = new_category
            state.user_corrected_category = True
            state.api_result = run_grounded_search(state)
            intake_assessment = state.api_result.get("intake_assessment", {})
            if not intake_assessment.get("can_proceed", True):
                state.current_state = "INIT"
                return (
                    f"{bot_message}\n\nThe updated category still needs better input. {intake_assessment.get('reason', '')}",
                    state,
                )
            state.final_report = run_editor_agent(
                {
                    **state.confirmed_category,
                    "product_page_url": state.product_link,
                    "confidence_notes": state.latest_vlm_check,
                },
                state.api_result,
            )
            bot_message += f"\n\n### Updated Safety Analysis\n\n{state.final_report}"

        return bot_message, state

    return "No runnable state is active. Press Start New Analysis to begin again.", state


def chat_wrapper(message, history, state, user_id, region, input_mode, link, direct_text, queue_for_review, review_notes, files):
    history = history or []
    bot_msg, updated_state = process_chat(
        message,
        history,
        state,
        user_id,
        region,
        input_mode,
        link,
        direct_text,
        queue_for_review,
        review_notes,
        files,
    )
    history.append((message, bot_msg))
    return history, updated_state, ""


with gr.Blocks(theme=gr.themes.Soft(), title="gemma4good vNext") as demo:
    session_state = gr.State()

    gr.Markdown("# gemma4good vNext (Gemma 4 product path)")
    gr.Markdown(
        "Agentic UX on top of a grounded core pipeline: choose one input mode, confirm the extracted text, align category/material, then retrieve grounded evidence."
    )
    gr.Markdown(
        f"Current shell: **{MAC_DEV.name}**. Portable target: **{PIXEL8_ANDROID.name}**.\n\n"
        "This Gradio app is the macOS development harness; the normalized payload and retrieval contract are the parts intended to carry forward to Pixel 8."
    )

    with gr.Row():
        with gr.Column(scale=1):
            user_id = gr.Textbox(label="User ID", value="local_demo_user")
            region = gr.Textbox(label="Region", value="California, USA")
            input_mode = gr.Radio(
                choices=[
                    ("Image(s) + product description", "image"),
                    ("Product URL", "url"),
                    ("Type product name / description", "text"),
                ],
                value="image",
                label="Input mode",
            )
            product_link = gr.Textbox(label="Product Page Link (used in URL mode)", placeholder="https://...")
            preview_url_btn = gr.Button("Preview URL fetch", variant="secondary")
            url_preview_box = gr.Textbox(label="URL fetch preview", lines=10, interactive=False)
            direct_text = gr.Textbox(
                label="Typed description / product text",
                lines=8,
                placeholder="In image mode, use this for a short product description if helpful. In text mode, paste the product name, ingredients, warning text, or product description here.",
            )
            input_files = gr.File(file_count="multiple", label="Upload 1-3 Label Images (used in image mode)")
            queue_for_review = gr.Checkbox(label="Queue this case for review", value=False)
            review_notes = gr.Textbox(label="Optional review notes", lines=2)
            reset_btn = gr.Button("Start New Analysis", variant="secondary")

        with gr.Column(scale=3):
            state_indicator = gr.Label(value="Status: Ready", label="Agent Activity", num_top_classes=0)
            chatbot = gr.Chatbot(height=520, show_label=False)
            msg = gr.Textbox(label="Your message", placeholder="Type 'yes' to confirm, or ask a follow-up question...")

    preview_url_btn.click(
        fn=preview_url_for_ui,
        inputs=[product_link, region],
        outputs=[url_preview_box],
    )

    msg.submit(
        fn=chat_wrapper,
        inputs=[msg, chatbot, session_state, user_id, region, input_mode, product_link, direct_text, queue_for_review, review_notes, input_files],
        outputs=[chatbot, session_state, msg],
    ).then(
        fn=lambda state: f"Status: {state.current_state} ({INPUT_MODES.get(state.input_mode, state.input_mode)})" if state else "Status: Ready",
        inputs=[session_state],
        outputs=[state_indicator],
    )

    def start_over():
        return [], SessionState(), "", "image", "", "", False, "", "", "Status: Ready"

    reset_btn.click(
        fn=start_over,
        outputs=[chatbot, session_state, msg, input_mode, product_link, direct_text, queue_for_review, review_notes, url_preview_box, state_indicator],
    )

    gr.HTML(
        """
        <div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px; font-size: 0.9em;">
            <b>Agentic intake rules:</b>
            <ul>
                <li>Image mode: if the OCR is too weak, the app should ask for better images or suggest URL / text mode.</li>
                <li>URL mode: if the page cannot be read, the app should ask for a corrected URL or suggest image / text mode.</li>
                <li>Text mode: if the description is too incomplete, the app should ask for more detail or recommend URL / image mode.</li>
            </ul>
        </div>
        """
    )


if __name__ == "__main__":
    demo.launch()
