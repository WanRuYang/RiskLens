from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class NormalizedProductPayload:
    product_name: str = ""
    product_page_url: str = ""
    raw_ocr_text: str = ""
    ingredient_text: str = ""
    nutrition_text: str = ""
    material_text: str = ""
    processing_method: str = ""
    packaging_material: str = ""
    processing_derivatives: str = "" # e.g. acrylamide, PAHs, nitrites
    concentration_assessment: str = "" # reasoning based on ingredient order
    warning_text: str = ""
    safety_caution_text: str = ""
    category_clues: str = ""
    region: str = "California, USA"
    input_mode: str = "image"
    user_question: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Stage2Decision:
    product_use_category: str = "unknown"
    material_or_form: str = "unknown"
    information_priority: str = "material_first"
    confidence_notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewSignal:
    user_corrected_text: bool = False
    user_corrected_category: bool = False
    queue_for_review: bool = False
    review_notes: str = ""
    review_reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GroundedQueryEnvelope:
    user_id: str = "local_demo_user"
    session_id: str = ""
    payload: NormalizedProductPayload = field(default_factory=NormalizedProductPayload)
    stage2: Stage2Decision = field(default_factory=Stage2Decision)
    review: ReviewSignal = field(default_factory=ReviewSignal)

    def as_api_payload(self) -> dict[str, Any]:
        payload = self.payload
        review = self.review
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "product_name": payload.product_name,
            "product_page_url": payload.product_page_url,
            "raw_ocr_text": payload.raw_ocr_text,
            "ingredients_text": " | ".join(
                part for part in [
                    payload.ingredient_text,
                    payload.material_text,
                    payload.processing_method,
                    payload.packaging_material,
                    payload.category_clues,
                ] if part
            ),
            "nutrition_text": payload.nutrition_text,
            "processing_derivatives": payload.processing_derivatives,
            "concentration_assessment": payload.concentration_assessment,
            "warning_text": " | ".join(
                part for part in [payload.warning_text, payload.safety_caution_text] if part
            ),
            "region": payload.region,
            "input_mode": payload.input_mode,
            "user_corrected_text": review.user_corrected_text,
            "user_corrected_category": review.user_corrected_category,
            "queue_for_review": review.queue_for_review,
            "review_notes": review.review_notes,
            "save_to_history": True,
        }
