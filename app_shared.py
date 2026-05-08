from __future__ import annotations

import json
import os
import uuid
from typing import Any

import requests

from vnext_contract import GroundedQueryEnvelope, NormalizedProductPayload, ReviewSignal, Stage2Decision


API_BASE_URL = os.getenv("GEMMA4GOOD_API_BASE_URL", "http://127.0.0.1:8010")


def safe_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def merge_nonempty(*parts: str) -> str:
    return " | ".join(part for part in parts if safe_text(part))


def ensure_stage2_decision(structured_data: dict[str, Any]) -> Stage2Decision:
    return Stage2Decision(
        product_use_category=safe_text(structured_data.get("product_use_category")) or "unknown",
        material_or_form=safe_text(structured_data.get("material_or_form")) or "unknown",
        information_priority=safe_text(structured_data.get("information_priority")) or "material_first",
        confidence_notes=safe_text(structured_data.get("confidence_notes")),
    )


def build_envelope(
    *,
    user_id: str,
    region: str,
    product_page_url: str,
    raw_ocr_text: str,
    structured_data: dict[str, Any],
    input_mode: str,
    user_question: str = "",
    user_corrected_text: bool = False,
    user_corrected_category: bool = False,
    queue_for_review: bool = False,
    review_notes: str = "",
) -> GroundedQueryEnvelope:
    normalized = NormalizedProductPayload(
        product_name=safe_text(structured_data.get("product_name")),
        product_page_url=safe_text(product_page_url),
        raw_ocr_text=safe_text(raw_ocr_text),
        ingredient_text=merge_nonempty(
            safe_text(structured_data.get("ingredient_text")),
            safe_text(structured_data.get("material_text")),
        ),
        warning_text=safe_text(structured_data.get("warning_text")),
        safety_caution_text=safe_text(structured_data.get("safety_caution_text")),
        category_clues=merge_nonempty(
            safe_text(structured_data.get("category_clues")),
            safe_text(structured_data.get("reasoning")),
        ),
        region=safe_text(region) or "California, USA",
        input_mode=safe_text(input_mode) or "image",
        user_question=safe_text(user_question),
    )
    review = ReviewSignal(
        user_corrected_text=user_corrected_text,
        user_corrected_category=user_corrected_category,
        queue_for_review=queue_for_review,
        review_notes=safe_text(review_notes),
    )
    return GroundedQueryEnvelope(
        user_id=safe_text(user_id) or "local_demo_user",
        session_id=str(uuid.uuid4()),
        payload=normalized,
        stage2=ensure_stage2_decision(structured_data),
        review=review,
    )


def call_local_api(payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(f"{API_BASE_URL}/analyze-product", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def preview_url(url: str, region: str = "California, USA") -> dict[str, Any]:
    response = requests.post(
        f"{API_BASE_URL}/preview-url",
        json={"product_page_url": safe_text(url), "region": safe_text(region) or "California, USA"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def check_local_api() -> tuple[bool, str]:
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - UI path
        return False, str(exc)
    return True, "ok"


def dump_debug_json(
    *,
    envelope: GroundedQueryEnvelope,
    structured_data: dict[str, Any],
    api_result: dict[str, Any],
    provider: str,
    raw_ocr_text: str,
) -> str:
    payload = {
        "provider": provider,
        "raw_ocr_text": raw_ocr_text,
        "structured_ocr": structured_data,
        "envelope": {
            "user_id": envelope.user_id,
            "session_id": envelope.session_id,
            "payload": envelope.payload.as_dict(),
            "stage2": envelope.stage2.as_dict(),
            "review": envelope.review.as_dict(),
            "api_payload": envelope.as_api_payload(),
        },
        "api_result": api_result,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
