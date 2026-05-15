from __future__ import annotations

import csv
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


DEFAULT_RECOMMENDATION_CSV = Path(
    "/Users/adelie/Documents/gemma4good/p65_data/processed/patterns/gemma_risk_recommendation_reference.csv"
)


def connect() -> psycopg.Connection:
    dsn = os.getenv("GEMMA4GOOD_PG_DSN") or "dbname=gemma4good"
    conn = psycopg.connect(dsn, row_factory=dict_row)
    with conn.cursor() as cur:
        cur.execute("SET search_path TO gemma4good, public;")
    conn.commit()
    return conn


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main() -> None:
    path = Path(os.getenv("GEMMA4GOOD_RECOMMENDATION_CSV", str(DEFAULT_RECOMMENDATION_CSV)))
    rows = load_rows(path)

    conn = connect()
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE serving_recommendations RESTART IDENTITY;")
                cur.executemany(
                    """
                    INSERT INTO serving_recommendations (
                        product_use_category,
                        material_subcategory,
                        coating_or_decoration_signal,
                        food_contact_signal,
                        child_use_signal,
                        heating_use_signal,
                        inhalation_signal,
                        total_unique_notices,
                        total_notice_rows,
                        top_chemical_families,
                        top_chemicals,
                        example_products,
                        recommendation_priority,
                        recommended_caution_text,
                        why_this_matters
                    )
                    VALUES (
                        %(product_use_category)s,
                        %(material_subcategory)s,
                        %(coating_or_decoration_signal)s,
                        %(food_contact_signal)s,
                        %(child_use_signal)s,
                        %(heating_use_signal)s,
                        %(inhalation_signal)s,
                        %(total_unique_notices)s,
                        %(total_notice_rows)s,
                        %(top_chemical_families)s,
                        %(top_chemicals)s,
                        %(example_products)s,
                        %(recommendation_priority)s,
                        %(recommended_caution_text)s,
                        %(why_this_matters)s
                    );
                    """,
                    rows,
                )
        conn.commit()
    finally:
        conn.close()

    print(f"Loaded serving recommendations: {len(rows)}")


if __name__ == "__main__":
    main()
