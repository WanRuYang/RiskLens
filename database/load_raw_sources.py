from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


DEFAULT_RAW_DATA_DIR = Path("/Users/adelie/Projects/gemma4good/data/data")


def slugify(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def normalize_text(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[\s/_-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def detect_authority(filename: str) -> str | None:
    lowered = filename.lower()
    mapping = [
        ("prop65", "OEHHA"),
        ("oehha", "OEHHA"),
        ("who", "WHO/IARC"),
        ("iarc", "WHO/IARC"),
        ("eu_", "European Union"),
        ("echa", "ECHA"),
        ("efsa", "EFSA"),
        ("fda", "FDA"),
        ("health_canada", "Health Canada"),
        ("cpsc", "CPSC"),
        ("epa", "EPA"),
        ("tsca", "EPA/TSCA"),
        ("jecfa", "JECFA"),
        ("codex", "Codex Alimentarius"),
    ]
    for token, label in mapping:
        if token in lowered:
            return label
    return None


def detect_jurisdiction(filename: str) -> str | None:
    lowered = filename.lower()
    mapping = [
        ("prop65", "California, USA"),
        ("us_", "United States"),
        ("fda", "United States"),
        ("cpsc", "United States"),
        ("epa", "United States"),
        ("tsca", "United States"),
        ("health_canada", "Canada"),
        ("eu_", "European Union"),
        ("echa", "European Union"),
        ("who", "Global"),
        ("iarc", "Global"),
        ("jecfa", "Global"),
        ("codex", "Global"),
    ]
    for token, label in mapping:
        if token in lowered:
            return label
    return None


def detect_source_category(filename: str) -> str:
    lowered = filename.lower()
    if "watchlist" in lowered:
        return "watchlist"
    if any(token in lowered for token in ["relevant_rules", "restricted", "prohibited", "hotlist", "annex"]):
        return "regulatory_rules"
    if any(token in lowered for token in ["food_additives", "food_contact", "tor_exemptions", "inventory"]):
        return "regulatory_dataset"
    if any(token in lowered for token in ["prop65", "iarc", "svhc"]):
        return "hazard_or_listing"
    return "raw_dataset"


def connect() -> psycopg.Connection[Any]:
    dsn = os.getenv("GEMMA4GOOD_PG_DSN") or "dbname=gemma4good"
    conn = psycopg.connect(dsn, row_factory=dict_row)
    with conn.cursor() as cur:
        cur.execute("SET search_path TO gemma4good, public;")
    conn.commit()
    return conn


def list_raw_files(raw_dir: Path) -> list[Path]:
    return sorted(path for path in raw_dir.glob("*.csv") if path.is_file())


def build_source_row(path: Path) -> dict[str, Any]:
    stem = path.stem
    filename = path.name
    return {
        "source_id": slugify(stem),
        "source_name": filename,
        "source_category": detect_source_category(filename),
        "authority": detect_authority(filename),
        "jurisdiction": detect_jurisdiction(filename),
        "file_path": str(path),
        "source_url": None,
        "source_version": None,
        "notes": "Auto-registered from local raw data directory.",
    }


def upsert_raw_source(conn: psycopg.Connection[Any], source: dict[str, Any]) -> None:
    sql = """
    INSERT INTO raw_sources (
        source_id, source_name, source_category, authority, jurisdiction,
        file_path, source_url, source_version, notes
    )
    VALUES (
        %(source_id)s, %(source_name)s, %(source_category)s, %(authority)s, %(jurisdiction)s,
        %(file_path)s, %(source_url)s, %(source_version)s, %(notes)s
    )
    ON CONFLICT (source_id) DO UPDATE SET
        source_name = EXCLUDED.source_name,
        source_category = EXCLUDED.source_category,
        authority = EXCLUDED.authority,
        jurisdiction = EXCLUDED.jurisdiction,
        file_path = EXCLUDED.file_path,
        source_url = EXCLUDED.source_url,
        source_version = EXCLUDED.source_version,
        notes = EXCLUDED.notes;
    """
    with conn.cursor() as cur:
        cur.execute(sql, source)


def start_ingest_run(conn: psycopg.Connection[Any], source_id: str, file_hash: str) -> int:
    sql = """
    INSERT INTO ingest_runs (
        source_id, ingest_label, file_hash, status
    )
    VALUES (%s, %s, %s, %s)
    RETURNING ingest_run_id;
    """
    label = f"raw_csv_ingest_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    with conn.cursor() as cur:
        cur.execute(sql, (source_id, label, file_hash, "started"))
        row = cur.fetchone()
        return int(row["ingest_run_id"])


def finish_ingest_run(conn: psycopg.Connection[Any], ingest_run_id: int, row_count: int, status: str = "completed") -> None:
    sql = """
    UPDATE ingest_runs
    SET row_count = %s,
        status = %s,
        completed_at = NOW()
    WHERE ingest_run_id = %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (row_count, status, ingest_run_id))


def delete_existing_records_for_source(conn: psycopg.Connection[Any], source_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM raw_records WHERE source_id = %s;", (source_id,))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def natural_key_for_row(row: dict[str, str], row_number: int) -> str:
    preferred_keys = [
        "cas_number",
        "substance_name",
        "preferred_name",
        "chemical_id",
        "evidence_id",
        "topic_id",
        "literature_id",
    ]
    values = [row.get(key, "") for key in preferred_keys if row.get(key, "")]
    if not values:
        values = [json.dumps(row, ensure_ascii=False, sort_keys=True)]
    base = "|".join(values) + f"|row={row_number}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def insert_raw_records(conn: psycopg.Connection[Any], source_id: str, ingest_run_id: int, rows: list[dict[str, str]]) -> int:
    sql = """
    INSERT INTO raw_records (
        source_id,
        ingest_run_id,
        source_row_number,
        natural_key,
        raw_payload,
        normalized_name_hint,
        cas_number_hint
    )
    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
    ON CONFLICT (source_id, source_row_number, ingest_run_id) DO UPDATE SET
        natural_key = EXCLUDED.natural_key,
        raw_payload = EXCLUDED.raw_payload,
        normalized_name_hint = EXCLUDED.normalized_name_hint,
        cas_number_hint = EXCLUDED.cas_number_hint;
    """

    payloads: list[tuple[Any, ...]] = []
    for idx, row in enumerate(rows, start=1):
        name_hint = (
            row.get("substance_name")
            or row.get("preferred_name")
            or row.get("topic_name")
            or row.get("regulation_or_list_name")
            or ""
        )
        cas_hint = row.get("cas_number") or ""
        payloads.append(
            (
                source_id,
                ingest_run_id,
                idx,
                natural_key_for_row(row, idx),
                json.dumps(row, ensure_ascii=False),
                normalize_text(name_hint) or None,
                cas_hint or None,
            )
        )

    chunk_size = 500
    with conn.cursor() as cur:
        for start in range(0, len(payloads), chunk_size):
            cur.executemany(sql, payloads[start : start + chunk_size])
    return len(payloads)


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def ingest_one_file(conn: psycopg.Connection[Any], path: Path) -> tuple[str, int]:
    source = build_source_row(path)
    upsert_raw_source(conn, source)
    file_hash = file_sha256(path)
    ingest_run_id = start_ingest_run(conn, source["source_id"], file_hash)
    delete_existing_records_for_source(conn, source["source_id"])
    rows = load_csv_rows(path)
    row_count = insert_raw_records(conn, source["source_id"], ingest_run_id, rows)
    finish_ingest_run(conn, ingest_run_id, row_count, "completed")
    return source["source_id"], row_count


def main() -> None:
    raw_dir = Path(os.getenv("GEMMA4GOOD_RAW_DATA_DIR", str(DEFAULT_RAW_DATA_DIR)))
    files = list_raw_files(raw_dir)
    if not files:
        raise SystemExit(f"No CSV files found under {raw_dir}")

    conn = connect()
    try:
        results: list[tuple[str, int]] = []
        for path in files:
            with conn.transaction():
                results.append(ingest_one_file(conn, path))
            conn.commit()
    finally:
        conn.close()

    total_rows = sum(count for _, count in results)
    print(f"Loaded raw sources: {len(results)}")
    print(f"Loaded raw records: {total_rows}")
    for source_id, count in results[:10]:
        print(f"{source_id}={count}")


if __name__ == "__main__":
    main()
