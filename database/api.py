from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field


CURRENT_DIR = Path(__file__).resolve().parent
BENCHMARK_PROJECT_ROOT = Path("/Users/adelie/Projects/gemma4good")
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
if str(BENCHMARK_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_PROJECT_ROOT))

import service


app = FastAPI(title="gemma4good local API", version="0.1.0")


class QueryContextRequest(BaseModel):
    product_text: Optional[str] = None
    product_page_url: Optional[str] = None
    ingredients_text: Optional[str] = None
    warning_text: Optional[str] = None
    region: Optional[str] = None


class AnalyzeProductRequest(BaseModel):
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    product_name: Optional[str] = None
    product_page_url: Optional[str] = None
    raw_ocr_text: Optional[str] = None
    ingredients_text: Optional[str] = None
    nutrition_text: Optional[str] = None
    warning_text: Optional[str] = None
    region: Optional[str] = None
    input_mode: Optional[str] = None
    user_corrected_text: bool = False
    user_corrected_category: bool = False
    queue_for_review: bool = False
    review_notes: Optional[str] = None
    save_to_history: bool = Field(default=True)


class PreviewUrlRequest(BaseModel):
    product_page_url: str
    region: Optional[str] = None


class IdentifyProductRequest(BaseModel):
    raw_text: str
    input_mode: str = "text"


class CuratedCorrectionRequest(BaseModel):
    correction_type: str
    original_value: Optional[str] = None
    corrected_value: str
    reviewer_notes: Optional[str] = None
    approved: bool = False


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/query-context")
def query_context(payload: QueryContextRequest) -> dict[str, Any]:
    conn = service.get_connection("dbname=gemma4good")
    try:
        return service.build_grounding_context(
            conn,
            product_text=payload.product_text,
            product_page_url=payload.product_page_url,
            ingredients_text=payload.ingredients_text,
            warning_text=payload.warning_text,
            region_label=payload.region,
        )
    finally:
        conn.close()


@app.post("/analyze-product")
@app.post("/analyze-product/")
def analyze_product(payload: AnalyzeProductRequest) -> dict[str, Any]:
    conn = service.get_connection("dbname=gemma4good")
    try:
        return service.analyze_product_for_app(
            conn,
            user_id=payload.user_id,
            session_id=payload.session_id,
            product_name=payload.product_name,
            product_page_url=payload.product_page_url,
            raw_ocr_text=payload.raw_ocr_text,
            ingredients_text=payload.ingredients_text,
            warning_text=payload.warning_text,
            region_label=payload.region,
            input_mode=payload.input_mode,
            user_corrected_text=payload.user_corrected_text,
            user_corrected_category=payload.user_corrected_category,
            queue_for_review=payload.queue_for_review,
            review_notes=payload.review_notes,
            save_to_history=payload.save_to_history,
        )
    finally:
        conn.close()


@app.post("/preview-url")
def preview_url(payload: PreviewUrlRequest) -> dict[str, Any]:
    url_context = service.fetch_product_page_context(payload.product_page_url)
    assessment = service.assess_input_sufficiency(
        input_mode="url",
        product_name=url_context.get("product_text", ""),
        raw_ocr_text="",
        ingredients_text=url_context.get("ingredients_text", ""),
        warning_text=url_context.get("warning_text", ""),
        product_page_url=payload.product_page_url,
        url_context=url_context,
    )
    return {
        "product_page_url": payload.product_page_url,
        "region": payload.region or "California, USA",
        "url_context": url_context,
        "intake_assessment": assessment,
    }


@app.post("/identify-product")
@app.post("/identify-product/")
def identify_product(payload: IdentifyProductRequest) -> dict[str, Any]:
    from mlx_engine import run_classifier_agent

    if not payload.raw_text.strip():
        raise HTTPException(status_code=400, detail="raw_text is required.")

    result = run_classifier_agent(payload.raw_text)

    # Forensic Parity: Ensure result matches Kotlin ProductIdentificationDto contract
    # Convert any list fields to joined strings for mobile client compatibility
    for key in ["ingredient_text", "nutrition_text", "material_text", "packaging_material", "processing_method", "processing_derivatives", "concentration_assessment", "warning_text", "safety_claims", "confidence_notes"]:
        val = result.get(key)
        if isinstance(val, list):
            result[key] = " | ".join(str(item) for item in val if item)
        elif val is None:
            result[key] = ""
        else:
            result[key] = str(val)

    return result


@app.get("/users/{user_id}/products")
def list_user_products(user_id: str) -> list[dict[str, Any]]:
    conn = service.get_connection("dbname=gemma4good")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    user_product_id,
                    created_at,
                    product_name,
                    product_page_url,
                    region_label,
                    matched_categories,
                    recommendation_bucket,
                    recommendation_summary
                FROM user_products
                WHERE user_id = %(user_id)s
                ORDER BY created_at DESC
                LIMIT 200;
                """,
                {"user_id": user_id},
            )
            return list(cur.fetchall())
    finally:
        conn.close()


@app.get("/users/{user_id}/chemicals")
def list_user_chemical_rollup(user_id: str) -> list[dict[str, Any]]:
    conn = service.get_connection("dbname=gemma4good")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    upc.chemical_id,
                    upc.preferred_name,
                    COUNT(DISTINCT upc.user_product_id) AS product_count
                FROM user_product_chemicals upc
                JOIN user_products up ON up.user_product_id = upc.user_product_id
                WHERE up.user_id = %(user_id)s
                GROUP BY upc.chemical_id, upc.preferred_name
                ORDER BY product_count DESC, upc.preferred_name ASC
                LIMIT 200;
                """,
                {"user_id": user_id},
            )
            return list(cur.fetchall())
    finally:
        conn.close()


@app.get("/users/{user_id}/products/{user_product_id}")
def get_user_product_detail(user_id: str, user_product_id: int) -> dict[str, Any]:
    conn = service.get_connection("dbname=gemma4good")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM user_products
                WHERE user_id = %(user_id)s
                  AND user_product_id = %(user_product_id)s;
                """,
                {"user_id": user_id, "user_product_id": user_product_id},
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Product record not found.")
            return dict(row)
    finally:
        conn.close()


@app.get("/benchmark/image-cases")
def list_benchmark_image_cases(
    segment: Optional[str] = Query(default=None),
    source_marketplace: Optional[str] = Query(default=None),
    category_group: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    conn = service.get_connection("dbname=gemma4good")
    try:
        where_clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if segment:
            where_clauses.append("segment = %(segment)s")
            params["segment"] = segment
        if source_marketplace:
            where_clauses.append("source_marketplace = %(source_marketplace)s")
            params["source_marketplace"] = source_marketplace
        if category_group:
            where_clauses.append("category_group = %(category_group)s")
            params["category_group"] = category_group

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"""
            SELECT
                case_id,
                source_marketplace,
                segment,
                category_group,
                product_title,
                marketplace_reference_url,
                front_image_path,
                ingredients_image_path,
                warning_image_path,
                capture_status,
                notes,
                created_at
            FROM benchmark_image_cases
            {where_sql}
            ORDER BY case_id ASC
            LIMIT %(limit)s;
        """
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = [dict(row) for row in cur.fetchall()]
        for row in rows:
            for key in ("front_image_path", "ingredients_image_path", "warning_image_path"):
                if row.get(key):
                    row[f"{key}_absolute"] = str((BENCHMARK_PROJECT_ROOT / row[key]).resolve())
        return rows
    finally:
        conn.close()


@app.get("/benchmark/image-cases/{case_id}")
def get_benchmark_image_case(case_id: str) -> dict[str, Any]:
    conn = service.get_connection("dbname=gemma4good")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    case_id,
                    source_marketplace,
                    segment,
                    category_group,
                    product_title,
                    marketplace_reference_url,
                    front_image_path,
                    ingredients_image_path,
                    warning_image_path,
                    capture_status,
                    notes,
                    created_at
                FROM benchmark_image_cases
                WHERE case_id = %(case_id)s;
                """,
                {"case_id": case_id},
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Benchmark image case not found.")
            result = dict(row)
        for key in ("front_image_path", "ingredients_image_path", "warning_image_path"):
            if result.get(key):
                result[f"{key}_absolute"] = str((BENCHMARK_PROJECT_ROOT / result[key]).resolve())
        return result
    finally:
        conn.close()


@app.get("/review-queue")
def list_review_queue(
    status: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    conn = service.get_connection("dbname=gemma4good")
    try:
        where_clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if status:
            where_clauses.append("status = %(status)s")
            params["status"] = status
        if priority:
            where_clauses.append("priority = %(priority)s")
            params["priority"] = priority
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"""
            SELECT
                review_id,
                created_at,
                status,
                priority,
                source_flow,
                user_id,
                session_id,
                input_mode,
                product_name,
                region_label,
                inferred_product_use_category,
                inferred_material_subcategory,
                recommendation_bucket,
                review_reasons,
                review_notes
            FROM review_queue
            {where_sql}
            ORDER BY created_at DESC
            LIMIT %(limit)s;
        """
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())
    finally:
        conn.close()


@app.get("/review-queue/{review_id}")
def get_review_queue_item(review_id: int) -> dict[str, Any]:
    conn = service.get_connection("dbname=gemma4good")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM review_queue WHERE review_id = %(review_id)s;", {"review_id": review_id})
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Review item not found.")
            return dict(row)
    finally:
        conn.close()


@app.post("/review-queue/{review_id}/corrections")
def add_curated_correction(review_id: int, payload: CuratedCorrectionRequest) -> dict[str, Any]:
    conn = service.get_connection("dbname=gemma4good")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT review_id FROM review_queue WHERE review_id = %(review_id)s;", {"review_id": review_id})
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Review item not found.")
            cur.execute(
                """
                INSERT INTO curated_corrections (
                    review_id,
                    correction_type,
                    original_value,
                    corrected_value,
                    reviewer_notes,
                    approved
                )
                VALUES (%(review_id)s, %(correction_type)s, %(original_value)s, %(corrected_value)s, %(reviewer_notes)s, %(approved)s)
                RETURNING correction_id;
                """,
                {
                    "review_id": review_id,
                    "correction_type": payload.correction_type,
                    "original_value": payload.original_value,
                    "corrected_value": payload.corrected_value,
                    "reviewer_notes": payload.reviewer_notes,
                    "approved": payload.approved,
                },
            )
            correction_id = int(cur.fetchone()["correction_id"])
            conn.commit()
            return {"correction_id": correction_id, "review_id": review_id, "status": "ok"}
    finally:
        conn.close()
