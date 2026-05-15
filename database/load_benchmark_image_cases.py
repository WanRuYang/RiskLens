import csv
import os
from pathlib import Path

import psycopg


DEFAULT_DB_NAME = os.getenv("GEMMA4GOOD_DB_NAME", "gemma4good")
DEFAULT_DB_USER = os.getenv("GEMMA4GOOD_DB_USER") or os.getenv("USER") or "postgres"
DEFAULT_DB_HOST = os.getenv("GEMMA4GOOD_DB_HOST", "localhost")
DEFAULT_DB_PORT = int(os.getenv("GEMMA4GOOD_DB_PORT", "5432"))
DEFAULT_MANIFEST_PATH = Path("/Users/adelie/Projects/gemma4good/benchmark_product_image_manifest.csv")


def connect() -> psycopg.Connection:
    return psycopg.connect(
        dbname=DEFAULT_DB_NAME,
        user=DEFAULT_DB_USER,
        host=DEFAULT_DB_HOST,
        port=DEFAULT_DB_PORT,
        row_factory=psycopg.rows.dict_row,
    )


def ensure_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS benchmark_image_cases (
                case_id TEXT PRIMARY KEY,
                source_marketplace TEXT,
                segment TEXT,
                category_group TEXT,
                product_title TEXT,
                marketplace_reference_url TEXT,
                front_image_path TEXT,
                ingredients_image_path TEXT,
                warning_image_path TEXT,
                capture_status TEXT,
                notes TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_benchmark_image_cases_segment
                ON benchmark_image_cases (segment, category_group);
            """
        )
    conn.commit()


def main() -> None:
    manifest_path = DEFAULT_MANIFEST_PATH
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with connect() as conn:
        ensure_table(conn)
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)

        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO benchmark_image_cases (
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
                        notes
                    )
                    VALUES (
                        %(case_id)s,
                        %(source_marketplace)s,
                        %(segment)s,
                        %(category_group)s,
                        %(product_title)s,
                        %(marketplace_reference_url)s,
                        %(front_image_path)s,
                        %(ingredients_image_path)s,
                        %(warning_image_path)s,
                        %(capture_status)s,
                        %(notes)s
                    )
                    ON CONFLICT (case_id) DO UPDATE SET
                        source_marketplace = EXCLUDED.source_marketplace,
                        segment = EXCLUDED.segment,
                        category_group = EXCLUDED.category_group,
                        product_title = EXCLUDED.product_title,
                        marketplace_reference_url = EXCLUDED.marketplace_reference_url,
                        front_image_path = EXCLUDED.front_image_path,
                        ingredients_image_path = EXCLUDED.ingredients_image_path,
                        warning_image_path = EXCLUDED.warning_image_path,
                        capture_status = EXCLUDED.capture_status,
                        notes = EXCLUDED.notes;
                    """,
                    row,
                )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM benchmark_image_cases;")
            count = cur.fetchone()["count"]

    print(f"Loaded {count} benchmark image cases from {manifest_path}")


if __name__ == "__main__":
    main()
