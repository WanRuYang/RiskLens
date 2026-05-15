from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

import psycopg


DB_DSN = "dbname=gemma4good"
PROJECT_ROOT = Path("/Users/adelie/Projects/gemma4good")
OUTPUT_ROOT = PROJECT_ROOT / "benchmark_images_real"
MANIFEST_PATH = PROJECT_ROOT / "benchmark_real_image_manifest.csv"

REAL_CASES = [
    {
        "case_id": "weee_real_001",
        "source_marketplace": "SayWeee",
        "segment": "food",
        "category_group": "seaweed_snack",
        "product_title": "Calbee Nori Shio 60g",
        "marketplace_reference_url": "https://www.sayweee.com/en/product/Calbee-Potato-Chips-Seaweed-Salt-60g/2903283",
        "image_mode": "weee_page",
    },
    {
        "case_id": "weee_real_002",
        "source_marketplace": "SayWeee",
        "segment": "food",
        "category_group": "ramune_soda",
        "product_title": "Ramune Carbonated Soft Drink 0.3L",
        "marketplace_reference_url": "https://www.sayweee.com/en/product/Japanese-Peach-Ramune-Marble-Soda/2886295",
        "image_mode": "weee_page",
    },
    {
        "case_id": "weee_real_003",
        "source_marketplace": "SayWeee",
        "segment": "food",
        "category_group": "drink_other",
        "product_title": "Fanale Original",
        "marketplace_reference_url": "https://www.sayweee.com/en/product/Mini-Mochi-Sweet-Rice-Cake-Original-Flavor/1992357/",
        "image_mode": "weee_page",
    },
    {
        "case_id": "amazon_real_001",
        "source_marketplace": "Amazon",
        "segment": "food",
        "category_group": "protein_drink",
        "product_title": "Premier Protein Chocolate 30g Protein 12 Pack",
        "marketplace_reference_url": "https://www.amazon.com/dp/B07MJL8NXR",
        "image_mode": "direct_image",
        "image_url": "https://m.media-amazon.com/images/I/51NQkAspSJL._SL1500_.jpg",
    },
    {
        "case_id": "amazon_real_002",
        "source_marketplace": "Amazon",
        "segment": "food",
        "category_group": "sparkling_water",
        "product_title": "Sparkling Ice Black Raspberry 12 Pack",
        "marketplace_reference_url": "https://www.amazon.com/dp/B01N05APQY",
        "image_mode": "direct_image",
        "image_url": "https://m.media-amazon.com/images/I/51YSg-W1xAL._SL1500_.jpg",
    },
    {
        "case_id": "amazon_real_003",
        "source_marketplace": "Amazon",
        "segment": "food",
        "category_group": "energy_drink",
        "product_title": "CELSIUS Live Fit Variety Pack 12 Pack",
        "marketplace_reference_url": "https://www.amazon.com/dp/B06X6J5266",
        "image_mode": "direct_image",
        "image_url": "https://m.media-amazon.com/images/I/61VfvfV69lL.jpg",
    },
]


def fetch_text(url: str) -> str:
    result = subprocess.run(
        [
            "curl",
            "--http1.1",
            "-L",
            "-A",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            url,
        ],
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def download_binary(url: str, destination: Path) -> None:
    subprocess.run(
        [
            "curl",
            "--http1.1",
            "-L",
            "-A",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            url,
            "-o",
            str(destination),
        ],
        check=True,
    )


def extract_weee_image_url(page_html: str) -> str:
    match = re.search(r'imageSrcSet="([^"]+)"', page_html)
    if not match:
        raise ValueError("Could not find imageSrcSet on SayWeee page.")
    first_entry = match.group(1).split(",")[0].strip()
    return first_entry.split(" ")[0]


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
    conn.commit()


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    rows_to_write: list[dict[str, str]] = []

    for case in REAL_CASES:
        case_dir = OUTPUT_ROOT / case["case_id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        front_path = case_dir / "front.png"

        if case["image_mode"] == "weee_page":
            html = fetch_text(case["marketplace_reference_url"])
            image_url = extract_weee_image_url(html)
        else:
            image_url = case["image_url"]

        download_binary(image_url, front_path)

        rows_to_write.append(
            {
                "case_id": case["case_id"],
                "source_marketplace": case["source_marketplace"],
                "segment": case["segment"],
                "category_group": case["category_group"],
                "product_title": case["product_title"],
                "marketplace_reference_url": case["marketplace_reference_url"],
                "front_image_path": str(front_path.relative_to(PROJECT_ROOT)),
                "ingredients_image_path": "",
                "warning_image_path": "",
                "capture_status": "real_front_image_downloaded",
                "notes": "Front product image downloaded from marketplace or marketplace-linked source. Ingredient and warning panels still needed.",
            }
        )

    with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "source_marketplace",
                "segment",
                "category_group",
                "product_title",
                "marketplace_reference_url",
                "front_image_path",
                "ingredients_image_path",
                "warning_image_path",
                "capture_status",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows_to_write)

    with psycopg.connect(DB_DSN, row_factory=psycopg.rows.dict_row) as conn:
        ensure_table(conn)
        with conn.cursor() as cur:
            for row in rows_to_write:
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

    print(f"Wrote real marketplace benchmark manifest: {MANIFEST_PATH}")
    print(f"Downloaded {len(rows_to_write)} real front images into {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
