from __future__ import annotations

import re
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


URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
INPUT_MODES = {
    "image": "images",
    "url": "product URL",
    "text": "typed text",
}
CLEAR_INPUT = {"text": "", "files": []}


@dataclass
class SessionState:
    user_id: str = "local_demo_user"
    region: str = "California, USA"
    current_state: str = "INIT"
    input_mode: str = "text"
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
        return "Please upload clearer product, ingredient, or warning images, or switch to a product URL / typed text."
    if mode == "url":
        return "Please re-enter the product URL. If the page still cannot be read, try product images or typed text instead."
    return "Please add more product detail, ingredients, or warning text. If that is hard to type, try a product URL or images instead."


def _extract_payload_parts(message_payload: Any) -> tuple[str, list[str]]:
    if isinstance(message_payload, str):
        return _safe_text(message_payload), []
    if not isinstance(message_payload, dict):
        return "", []

    text = _safe_text(message_payload.get("text"))
    raw_files = message_payload.get("files") or []
    file_paths: list[str] = []
    for item in raw_files:
        if isinstance(item, str):
            file_paths.append(item)
        elif isinstance(item, dict):
            path = item.get("path") or item.get("name")
            if path:
                file_paths.append(path)
        elif hasattr(item, "path") and getattr(item, "path"):
            file_paths.append(getattr(item, "path"))
        elif hasattr(item, "name") and getattr(item, "name"):
            file_paths.append(getattr(item, "name"))
    return text, file_paths[:3]


def _first_url(text: str) -> str:
    match = URL_RE.search(text or "")
    return match.group(0) if match else ""


def _strip_urls(text: str) -> str:
    return URL_RE.sub("", text or "").strip()


def _detect_input_mode(text: str, file_paths: list[str]) -> str:
    if file_paths:
        return "image"
    if _first_url(text):
        return "url"
    return "text"


def _format_turn_summary(text: str, file_paths: list[str]) -> str:
    parts: list[str] = []
    clean = _safe_text(text)
    if clean:
        parts.append(clean)
    if file_paths:
        parts.append(f"[attached {len(file_paths)} image(s)]")
    return "\n".join(parts).strip() or "[empty input]"


def _format_url_preview(preview: dict[str, Any]) -> str:
    url_context = preview.get("url_context", {})
    assessment = preview.get("intake_assessment", {})
    header = [
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
    return "\n".join(header + ([""] if body else []) + ([body] if body else [])).strip()


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
    sections: list[tuple[str, str]] = []

    if state.input_mode == "image":
        if not state.image_paths:
            return False, "I still need at least one readable product image."
        ocr_text = run_scribe_agent(state.image_paths)
        if _looks_sparse(ocr_text, threshold=15):
            return False, "I could not read enough text from the uploaded images."
        sections.append(("OCR From Images", ocr_text))
        if state.direct_text:
            sections.append(("User Notes", state.direct_text))
        state.raw_ocr_text = _join_sections(sections)
        return True, state.raw_ocr_text

    if state.input_mode == "url":
        if not state.product_link:
            return False, "I need a product page URL to continue."
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
        if state.direct_text:
            sections.append(("User Notes", state.direct_text))
        state.raw_ocr_text = _join_sections(sections)
        return True, state.raw_ocr_text

    if not state.direct_text:
        return False, "I need more text about the product to continue."
    if _looks_sparse(state.direct_text, threshold=25):
        return False, "The typed text is still too short to analyze reliably."
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


def _set_new_turn(state: SessionState, message_payload: Any) -> tuple[str, list[str]]:
    text, file_paths = _extract_payload_parts(message_payload)
    detected_mode = _detect_input_mode(text, file_paths)
    state.input_mode = detected_mode
    state.image_paths = file_paths
    state.product_link = _first_url(text) if detected_mode == "url" else ""
    state.direct_text = _strip_urls(text) if detected_mode == "url" else _safe_text(text)
    state.raw_ocr_text = ""
    state.confirmed_text = ""
    state.proposed_category = {}
    state.confirmed_category = {}
    state.api_result = {}
    state.final_report = ""
    state.latest_vlm_check = "N/A"
    state.url_preview = {}
    state.user_corrected_text = False
    state.user_corrected_category = False
    return text, file_paths


def process_chat(
    message_payload: Any,
    history: list[tuple[str, str]],
    state: SessionState | None,
    user_id_val: str,
    region_val: str,
    queue_for_review_val: bool,
    review_notes_val: str,
):
    if state is None:
        state = SessionState()

    state.user_id = _safe_text(user_id_val) or state.user_id
    state.region = _safe_text(region_val) or state.region
    state.queue_for_review = bool(queue_for_review_val)
    state.review_notes = _safe_text(review_notes_val)

    incoming_text, incoming_files = _extract_payload_parts(message_payload)
    clean_message = _safe_text(incoming_text)

    if state.current_state == "INIT":
        _set_new_turn(state, message_payload)
        ok, intake_text = collect_mode_input(state)
        if not ok:
            return (
                f"I need better {INPUT_MODES.get(state.input_mode, 'input')} before I can continue.\n\n"
                f"Reason: {ok and '' or intake_text}\n\n"
                f"Next step: {_mode_specific_guidance(state.input_mode)}",
                state,
            )

        state.current_state = "AWAITING_TEXT_CONFIRM"
        preview_prefix = ""
        if state.input_mode == "url" and state.url_preview:
            preview_prefix = f"### URL Fetch Preview\n\n{_format_url_preview(state.url_preview)}\n\n---\n\n"
        return (
            f"{preview_prefix}I collected the first-pass product text from your {INPUT_MODES.get(state.input_mode, 'input')}. Please confirm it before I classify and search.\n\n"
            f"**Extracted / Combined Text:**\n{intake_text}\n\n"
            "Reply `yes` if this looks right, or paste corrected text.",
            state,
        )

    if state.current_state == "AWAITING_TEXT_CONFIRM":
        if incoming_files or (_first_url(clean_message) and clean_message.lower() not in {"yes", "y", "correct", "ok"}):
            state.current_state = "INIT"
            return process_chat(message_payload, history, state, state.user_id, state.region, state.queue_for_review, state.review_notes)

        if clean_message.lower() in {"yes", "y", "correct", "ok"}:
            state.confirmed_text = state.raw_ocr_text
            state.user_corrected_text = False
        else:
            state.confirmed_text = clean_message
            state.user_corrected_text = True

        if state.input_mode == "text" and _looks_sparse(state.confirmed_text, threshold=25):
            state.current_state = "INIT"
            return (
                "The typed text is still too incomplete for a grounded answer. Please add more detail, or switch to a product URL or images.",
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
        if incoming_files or (_first_url(clean_message) and clean_message.lower() not in {"yes", "y", "correct", "ok"}):
            state.current_state = "INIT"
            return process_chat(message_payload, history, state, state.user_id, state.region, state.queue_for_review, state.review_notes)

        if clean_message.lower() in {"yes", "y", "correct", "ok"}:
            state.confirmed_category = dict(state.proposed_category)
            state.user_corrected_category = False
        else:
            state.confirmed_category = dict(state.proposed_category)
            state.confirmed_category["product_use_category"] = clean_message or state.proposed_category.get("product_use_category", "unknown")
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
            f"### Final Safety Analysis\n\n{state.final_report}\n\n---\nYou can ask follow-up questions, attach clearer images, or paste a new URL / product description to start a new analysis.",
            state,
        )

    if state.current_state == "FEEDBACK":
        if incoming_files or _first_url(clean_message):
            state.current_state = "INIT"
            return process_chat(message_payload, history, state, state.user_id, state.region, state.queue_for_review, state.review_notes)

        action = "NONE"
        feedback_result: dict[str, Any] = {}

        if clean_message.lower() == "rerun":
            action = "RERUN_SEARCH"
            feedback_result = {"action_payload": {}}
            bot_message = "Understood. I will rerun the grounded search with the current text."
        else:
            feedback_result = run_feedback_agent(clean_message, {"api_result": state.api_result, "report": state.final_report})
            bot_message = feedback_result.get(
                "response",
                "I can help rerun with a different region, ingredient clue, or you can paste a new URL / product description for a new analysis.",
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


def chat_wrapper(message_payload, history, state, user_id, region, queue_for_review, review_notes):
    history = history or []
    user_text, user_files = _extract_payload_parts(message_payload)
    bot_msg, updated_state = process_chat(
        message_payload,
        history,
        state,
        user_id,
        region,
        queue_for_review,
        review_notes,
    )
    history.append((_format_turn_summary(user_text, user_files), bot_msg))
    return history, updated_state, CLEAR_INPUT


with gr.Blocks(title="gemma4good vNext") as demo:
    session_state = gr.State(SessionState())

    gr.Markdown("# gemma4good")
    gr.Markdown(
        "Send a product URL, type a product name/description, or attach up to 3 images such as the product front, ingredients panel, a Prop 65 warning sticker, or phone-camera photos. The app will decide how to process the input behind the scenes."
    )
    gr.Markdown(
        f"Current shell: **{MAC_DEV.name}**. Portable target: **{PIXEL8_ANDROID.name}**. This desktop UI is the macOS development harness; OpenAI remains benchmark-only and is not part of the product path."
    )

    with gr.Accordion("Settings", open=False):
        user_id = gr.Textbox(label="User ID", value="local_demo_user")
        region = gr.Textbox(label="Region", value="California, USA")
        queue_for_review = gr.Checkbox(label="Queue this case for review", value=False)
        review_notes = gr.Textbox(label="Optional review notes", lines=2)

    chatbot = gr.Chatbot(height=560, show_label=False)
    composer = gr.MultimodalTextbox(
        file_count="multiple",
        file_types=[".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif"],
        placeholder="Type product text, paste a product URL, or attach up to 3 images…",
        label="",
    )
    reset_btn = gr.Button("Start New Analysis", variant="secondary")

    composer.submit(
        fn=chat_wrapper,
        inputs=[composer, chatbot, session_state, user_id, region, queue_for_review, review_notes],
        outputs=[chatbot, session_state, composer],
    )

    def start_over():
        return [], SessionState(), CLEAR_INPUT

    reset_btn.click(
        fn=start_over,
        outputs=[chatbot, session_state, composer],
    )


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
