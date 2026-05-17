from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row


DEFAULT_APP_DATA_DIR = Path("/Users/adelie/Projects/gemma4good/data/app_data")


def normalize_text(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[\s/_-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def split_multi_value(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"\s*[;|]\s*", value.strip())
    cleaned = [part.strip() for part in parts if part.strip()]
    seen: set[str] = set()
    ordered: list[str] = []
    for item in cleaned:
        lowered = item.casefold()
        if lowered not in seen:
            seen.add(lowered)
            ordered.append(item)
    return ordered


def parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    text = value.strip().lower()
    if text in {"yes", "true", "1"}:
        return True
    if text in {"no", "false", "0"}:
        return False
    return None


def infer_status_flags(status: str | None, source_authority: str | None) -> dict[str, bool]:
    text = (status or "").strip().lower()
    source = (source_authority or "").strip().lower()
    return {
        "warning_flag": "warning" in text or "prop 65" in source or "listed" in text and "oehha" in source,
        "ban_flag": any(token in text for token in ["banned", "prohibited", "ban"]),
        "restriction_flag": any(token in text for token in ["restricted", "limit", "maximum", "not permitted in some uses"]),
        "allowed_flag": any(token in text for token in ["allowed", "authorized", "authorised", "permitted", "gras"]),
        "hazard_classification_flag": any(token in text for token in ["group 1", "group 2", "hazard", "listed"]),
    }


def connect() -> psycopg.Connection[Any]:
    dsn = os.getenv("GEMMA4GOOD_PG_DSN") or "dbname=gemma4good"
    conn = psycopg.connect(dsn, row_factory=dict_row)
    with conn.cursor() as cur:
        cur.execute("SET search_path TO gemma4good, public;")
    conn.commit()
    return conn


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def upsert_chemicals(conn: psycopg.Connection[Any], rows: list[dict[str, str]]) -> tuple[int, int]:
    inserted = 0
    alias_rows: list[tuple[str, str, str, str, bool]] = []
    sql = """
    INSERT INTO chemicals (
        chemical_id,
        preferred_name,
        normalized_name,
        cas_number,
        consumer_concern_groups,
        primary_health_concerns,
        common_product_types,
        likely_material_layers,
        source_priority_level,
        evidence_summary,
        ambiguity_notes,
        seed_sources
    )
    VALUES (
        %(chemical_id)s,
        %(preferred_name)s,
        %(normalized_name)s,
        %(cas_number)s,
        %(consumer_concern_groups)s,
        %(primary_health_concerns)s,
        %(common_product_types)s,
        %(likely_material_layers)s,
        %(source_priority_level)s,
        %(evidence_summary)s,
        %(ambiguity_notes)s,
        %(seed_sources)s
    )
    ON CONFLICT (chemical_id) DO UPDATE SET
        preferred_name = EXCLUDED.preferred_name,
        normalized_name = EXCLUDED.normalized_name,
        cas_number = EXCLUDED.cas_number,
        consumer_concern_groups = EXCLUDED.consumer_concern_groups,
        primary_health_concerns = EXCLUDED.primary_health_concerns,
        common_product_types = EXCLUDED.common_product_types,
        likely_material_layers = EXCLUDED.likely_material_layers,
        source_priority_level = EXCLUDED.source_priority_level,
        evidence_summary = EXCLUDED.evidence_summary,
        ambiguity_notes = EXCLUDED.ambiguity_notes,
        seed_sources = EXCLUDED.seed_sources,
        updated_at = NOW();
    """
    with conn.cursor() as cur:
        for row in rows:
            payload = {
                "chemical_id": row["chemical_id"],
                "preferred_name": row["preferred_name"],
                "normalized_name": normalize_text(row["preferred_name"]),
                "cas_number": row.get("cas_number") or None,
                "consumer_concern_groups": json.dumps(split_multi_value(row.get("consumer_concern_groups"))),
                "primary_health_concerns": json.dumps(split_multi_value(row.get("primary_health_concerns"))),
                "common_product_types": json.dumps(split_multi_value(row.get("common_product_types"))),
                "likely_material_layers": json.dumps(split_multi_value(row.get("likely_material_layers"))),
                "source_priority_level": row.get("source_priority_level") or None,
                "evidence_summary": row.get("evidence_summary") or None,
                "ambiguity_notes": row.get("ambiguity_notes") or None,
                "seed_sources": json.dumps(split_multi_value(row.get("seed_sources"))),
            }
            cur.execute(sql, payload)
            inserted += 1

            aliases = split_multi_value(row.get("synonyms"))
            for alias in aliases:
                alias_rows.append(
                    (
                        row["chemical_id"],
                        alias,
                        normalize_text(alias),
                        "synonym",
                        False,
                    )
                )

    alias_inserted = 0
    if alias_rows:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO chemical_aliases (
                    chemical_id, alias_text, normalized_alias, alias_type, is_primary
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (chemical_id, normalized_alias) DO NOTHING;
                """,
                alias_rows,
            )
            alias_inserted = len(alias_rows)
    return inserted, alias_inserted


def upsert_product_types(conn: psycopg.Connection[Any], rows: list[dict[str, str]]) -> tuple[int, int]:
    inserted = 0
    alias_rows: list[tuple[str, str, str, str]] = []
    sql = """
    INSERT INTO product_types (
        product_type_id,
        normalized_product_type,
        mapped_product_category,
        likely_material_layers,
        high_priority_concern_groups,
        likely_regulatory_datasets,
        warning_guidance_short,
        what_to_ask_or_scan_next,
        priority_level
    )
    VALUES (
        %(product_type_id)s,
        %(normalized_product_type)s,
        %(mapped_product_category)s,
        %(likely_material_layers)s,
        %(high_priority_concern_groups)s,
        %(likely_regulatory_datasets)s,
        %(warning_guidance_short)s,
        %(what_to_ask_or_scan_next)s,
        %(priority_level)s
    )
    ON CONFLICT (product_type_id) DO UPDATE SET
        normalized_product_type = EXCLUDED.normalized_product_type,
        mapped_product_category = EXCLUDED.mapped_product_category,
        likely_material_layers = EXCLUDED.likely_material_layers,
        high_priority_concern_groups = EXCLUDED.high_priority_concern_groups,
        likely_regulatory_datasets = EXCLUDED.likely_regulatory_datasets,
        warning_guidance_short = EXCLUDED.warning_guidance_short,
        what_to_ask_or_scan_next = EXCLUDED.what_to_ask_or_scan_next,
        priority_level = EXCLUDED.priority_level,
        updated_at = NOW();
    """
    with conn.cursor() as cur:
        for row in rows:
            payload = {
                "product_type_id": row["product_type_id"],
                "normalized_product_type": normalize_text(row["normalized_product_type"]),
                "mapped_product_category": row["mapped_product_category"],
                "likely_material_layers": json.dumps(split_multi_value(row.get("likely_material_layers"))),
                "high_priority_concern_groups": json.dumps(split_multi_value(row.get("high_priority_concern_groups"))),
                "likely_regulatory_datasets": json.dumps(split_multi_value(row.get("likely_regulatory_datasets"))),
                "warning_guidance_short": row.get("warning_guidance_short") or None,
                "what_to_ask_or_scan_next": row.get("what_to_ask_or_scan_next") or None,
                "priority_level": row.get("priority_level") or None,
            }
            cur.execute(sql, payload)
            inserted += 1

            alias_rows.append(
                (
                    row["product_type_id"],
                    row["normalized_product_type"],
                    normalize_text(row["normalized_product_type"]),
                    "normalized_product_type",
                )
            )
            for alias in split_multi_value(row.get("consumer_aliases")):
                alias_rows.append(
                    (
                        row["product_type_id"],
                        alias,
                        normalize_text(alias),
                        "consumer_alias",
                    )
                )

    alias_inserted = 0
    if alias_rows:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO product_type_aliases (
                    product_type_id, alias_text, normalized_alias, alias_source
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (product_type_id, normalized_alias) DO NOTHING;
                """,
                alias_rows,
            )
            alias_inserted = len(alias_rows)
    return inserted, alias_inserted


def upsert_regulatory_evidence(conn: psycopg.Connection[Any], rows: list[dict[str, str]]) -> int:
    sql = """
    INSERT INTO regulatory_evidence (
        evidence_id,
        chemical_id,
        preferred_name,
        normalized_preferred_name,
        source_dataset_id,
        source_authority,
        source_type,
        country_or_jurisdiction,
        region_label,
        product_category,
        product_scope,
        regulation_or_list_name,
        regulatory_status,
        hazard_basis,
        warning_flag,
        ban_flag,
        restriction_flag,
        allowed_flag,
        hazard_classification_flag,
        threshold_value,
        threshold_unit,
        threshold_conditions,
        citation_url,
        citation_title,
        source_row_reference,
        evidence_type,
        consumer_concern_groups
    )
    VALUES (
        %(evidence_id)s,
        %(chemical_id)s,
        %(preferred_name)s,
        %(normalized_preferred_name)s,
        %(source_dataset_id)s,
        %(source_authority)s,
        %(source_type)s,
        %(country_or_jurisdiction)s,
        %(region_label)s,
        %(product_category)s,
        %(product_scope)s,
        %(regulation_or_list_name)s,
        %(regulatory_status)s,
        %(hazard_basis)s,
        %(warning_flag)s,
        %(ban_flag)s,
        %(restriction_flag)s,
        %(allowed_flag)s,
        %(hazard_classification_flag)s,
        %(threshold_value)s,
        %(threshold_unit)s,
        %(threshold_conditions)s,
        %(citation_url)s,
        %(citation_title)s,
        %(source_row_reference)s,
        %(evidence_type)s,
        %(consumer_concern_groups)s
    )
    ON CONFLICT (evidence_id) DO UPDATE SET
        chemical_id = EXCLUDED.chemical_id,
        preferred_name = EXCLUDED.preferred_name,
        normalized_preferred_name = EXCLUDED.normalized_preferred_name,
        source_dataset_id = EXCLUDED.source_dataset_id,
        source_authority = EXCLUDED.source_authority,
        source_type = EXCLUDED.source_type,
        country_or_jurisdiction = EXCLUDED.country_or_jurisdiction,
        region_label = EXCLUDED.region_label,
        product_category = EXCLUDED.product_category,
        product_scope = EXCLUDED.product_scope,
        regulation_or_list_name = EXCLUDED.regulation_or_list_name,
        regulatory_status = EXCLUDED.regulatory_status,
        hazard_basis = EXCLUDED.hazard_basis,
        warning_flag = EXCLUDED.warning_flag,
        ban_flag = EXCLUDED.ban_flag,
        restriction_flag = EXCLUDED.restriction_flag,
        allowed_flag = EXCLUDED.allowed_flag,
        hazard_classification_flag = EXCLUDED.hazard_classification_flag,
        threshold_value = EXCLUDED.threshold_value,
        threshold_unit = EXCLUDED.threshold_unit,
        threshold_conditions = EXCLUDED.threshold_conditions,
        citation_url = EXCLUDED.citation_url,
        citation_title = EXCLUDED.citation_title,
        source_row_reference = EXCLUDED.source_row_reference,
        evidence_type = EXCLUDED.evidence_type,
        consumer_concern_groups = EXCLUDED.consumer_concern_groups;
    """
    count = 0
    with conn.cursor() as cur:
        for row in rows:
            flags = infer_status_flags(row.get("regulatory_status"), row.get("source_authority"))
            payload = {
                "evidence_id": row["evidence_id"],
                "chemical_id": row.get("chemical_id") or None,
                "preferred_name": row["preferred_name"],
                "normalized_preferred_name": normalize_text(row["preferred_name"]),
                "source_dataset_id": row.get("source_dataset_id") or None,
                "source_authority": row["source_authority"],
                "source_type": row.get("evidence_type") or None,
                "country_or_jurisdiction": row.get("country_or_jurisdiction") or None,
                "region_label": row.get("country_or_jurisdiction") or None,
                "product_category": row.get("product_category") or None,
                "product_scope": row.get("product_scope") or None,
                "regulation_or_list_name": row["regulation_or_list_name"],
                "regulatory_status": row["regulatory_status"],
                "hazard_basis": row.get("hazard_basis") or None,
                "warning_flag": flags["warning_flag"],
                "ban_flag": flags["ban_flag"],
                "restriction_flag": flags["restriction_flag"],
                "allowed_flag": flags["allowed_flag"],
                "hazard_classification_flag": flags["hazard_classification_flag"],
                "threshold_value": row.get("threshold_value") or None,
                "threshold_unit": row.get("threshold_unit") or None,
                "threshold_conditions": row.get("threshold_conditions") or None,
                "citation_url": row.get("citation_url") or None,
                "citation_title": row.get("citation_title") or None,
                "source_row_reference": row.get("source_row_reference") or None,
                "evidence_type": row.get("evidence_type") or None,
                "consumer_concern_groups": json.dumps(split_multi_value(row.get("consumer_concern_groups"))),
            }
            cur.execute(sql, payload)
            count += 1
    return count


def upsert_literature(conn: psycopg.Connection[Any], rows: list[dict[str, str]]) -> int:
    sql = """
    INSERT INTO literature_evidence (
        literature_id,
        topic_id,
        topic_name,
        chemical_or_material_scope,
        evidence_role,
        evidence_type,
        evidence_strength,
        stance_direction,
        jurisdiction_or_body,
        consumer_context,
        claim_summary,
        important_limitations,
        citation_title,
        citation_url,
        publisher_or_journal,
        publication_year,
        source_type,
        recommended_for_consumer_quote
    )
    VALUES (
        %(literature_id)s,
        %(topic_id)s,
        %(topic_name)s,
        %(chemical_or_material_scope)s,
        %(evidence_role)s,
        %(evidence_type)s,
        %(evidence_strength)s,
        %(stance_direction)s,
        %(jurisdiction_or_body)s,
        %(consumer_context)s,
        %(claim_summary)s,
        %(important_limitations)s,
        %(citation_title)s,
        %(citation_url)s,
        %(publisher_or_journal)s,
        %(publication_year)s,
        %(source_type)s,
        %(recommended_for_consumer_quote)s
    )
    ON CONFLICT (literature_id) DO UPDATE SET
        topic_id = EXCLUDED.topic_id,
        topic_name = EXCLUDED.topic_name,
        chemical_or_material_scope = EXCLUDED.chemical_or_material_scope,
        evidence_role = EXCLUDED.evidence_role,
        evidence_type = EXCLUDED.evidence_type,
        evidence_strength = EXCLUDED.evidence_strength,
        stance_direction = EXCLUDED.stance_direction,
        jurisdiction_or_body = EXCLUDED.jurisdiction_or_body,
        consumer_context = EXCLUDED.consumer_context,
        claim_summary = EXCLUDED.claim_summary,
        important_limitations = EXCLUDED.important_limitations,
        citation_title = EXCLUDED.citation_title,
        citation_url = EXCLUDED.citation_url,
        publisher_or_journal = EXCLUDED.publisher_or_journal,
        publication_year = EXCLUDED.publication_year,
        source_type = EXCLUDED.source_type,
        recommended_for_consumer_quote = EXCLUDED.recommended_for_consumer_quote;
    """
    count = 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                sql,
                {
                    **row,
                    "recommended_for_consumer_quote": parse_bool(row.get("recommended_for_consumer_quote")),
                },
            )
            count += 1
    return count


def upsert_controversy_topics(conn: psycopg.Connection[Any], rows: list[dict[str, str]]) -> int:
    sql = """
    INSERT INTO controversy_topics (
        topic_id,
        topic_name,
        consumer_question,
        why_controversial,
        what_regulation_says,
        what_literature_says,
        how_gemma_should_frame_it,
        priority_level,
        primary_source_urls
    )
    VALUES (
        %(topic_id)s,
        %(topic_name)s,
        %(consumer_question)s,
        %(why_controversial)s,
        %(what_regulation_says)s,
        %(what_literature_says)s,
        %(how_gemma_should_frame_it)s,
        %(priority_level)s,
        %(primary_source_urls)s
    )
    ON CONFLICT (topic_id) DO UPDATE SET
        topic_name = EXCLUDED.topic_name,
        consumer_question = EXCLUDED.consumer_question,
        why_controversial = EXCLUDED.why_controversial,
        what_regulation_says = EXCLUDED.what_regulation_says,
        what_literature_says = EXCLUDED.what_literature_says,
        how_gemma_should_frame_it = EXCLUDED.how_gemma_should_frame_it,
        priority_level = EXCLUDED.priority_level,
        primary_source_urls = EXCLUDED.primary_source_urls;
    """
    count = 0
    with conn.cursor() as cur:
        for row in rows:
            payload = {
                **row,
                "primary_source_urls": json.dumps(split_multi_value(row.get("primary_source_urls"))),
            }
            cur.execute(sql, payload)
            count += 1
    return count


def upsert_warning_interpretations(conn: psycopg.Connection[Any], rows: list[dict[str, str]]) -> int:
    count = 0
    sql = """
    INSERT INTO warning_interpretations (
        warning_id,
        regime,
        warning_text_pattern,
        normalized_warning_text_pattern,
        product_context,
        concern_level_default,
        what_it_legally_means,
        what_it_does_not_mean,
        when_to_take_more_seriously,
        when_not_to_overinterpret,
        suggested_user_action
    )
    VALUES (
        %(warning_id)s,
        %(regime)s,
        %(warning_text_pattern)s,
        %(normalized_warning_text_pattern)s,
        %(product_context)s,
        %(concern_level_default)s,
        %(what_it_legally_means)s,
        %(what_it_does_not_mean)s,
        %(when_to_take_more_seriously)s,
        %(when_not_to_overinterpret)s,
        %(suggested_user_action)s
    )
    ON CONFLICT (warning_id) DO UPDATE SET
        regime = EXCLUDED.regime,
        warning_text_pattern = EXCLUDED.warning_text_pattern,
        normalized_warning_text_pattern = EXCLUDED.normalized_warning_text_pattern,
        product_context = EXCLUDED.product_context,
        concern_level_default = EXCLUDED.concern_level_default,
        what_it_legally_means = EXCLUDED.what_it_legally_means,
        what_it_does_not_mean = EXCLUDED.what_it_does_not_mean,
        when_to_take_more_seriously = EXCLUDED.when_to_take_more_seriously,
        when_not_to_overinterpret = EXCLUDED.when_not_to_overinterpret,
        suggested_user_action = EXCLUDED.suggested_user_action;
    """
    with conn.cursor() as cur:
        for row in rows:
            payload = {
                **row,
                "normalized_warning_text_pattern": normalize_text(row["warning_text_pattern"]),
            }
            cur.execute(sql, payload)
            count += 1
    return count


def make_warning_id(regime: str, pattern: str) -> str:
    digest = hashlib.sha1(f"{regime}|{pattern}".encode("utf-8")).hexdigest()[:12]
    return f"warn_{digest}"


def ensure_warning_ids(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    fixed: list[dict[str, str]] = []
    for row in rows:
        item = dict(row)
        item["warning_id"] = row.get("warning_id") or make_warning_id(row["regime"], row["warning_text_pattern"])
        fixed.append(item)
    return fixed


def main() -> None:
    app_dir = Path(os.getenv("GEMMA4GOOD_APP_DATA_DIR", str(DEFAULT_APP_DATA_DIR)))
    files = {
        "chemical_master": app_dir / "chemical_master.csv",
        "priority_chemical_overrides": app_dir / "priority_chemical_overrides.csv",
        "product_risk_mapping": app_dir / "product_risk_mapping.csv",
        "regulatory_evidence": app_dir / "regulatory_evidence.csv",
        "priority_regulatory_evidence": app_dir / "priority_regulatory_evidence.csv",
        "literature_evidence": app_dir / "literature_evidence.csv",
        "controversy_topic_briefs": app_dir / "controversy_topic_briefs.csv",
        "warning_interpretation": app_dir / "warning_interpretation.csv",
    }

    conn = connect()
    try:
        with conn.transaction():
            chemical_rows = load_csv(files["chemical_master"])
            if files["priority_chemical_overrides"].exists():
                chemical_rows.extend(load_csv(files["priority_chemical_overrides"]))
            chemical_count, chemical_alias_count = upsert_chemicals(conn, chemical_rows)

            product_rows = load_csv(files["product_risk_mapping"])
            product_count, product_alias_count = upsert_product_types(conn, product_rows)

            regulatory_rows = load_csv(files["regulatory_evidence"])
            if files["priority_regulatory_evidence"].exists():
                regulatory_rows.extend(load_csv(files["priority_regulatory_evidence"]))
            regulatory_count = upsert_regulatory_evidence(conn, regulatory_rows)
            literature_count = upsert_literature(conn, load_csv(files["literature_evidence"]))
            topic_count = upsert_controversy_topics(conn, load_csv(files["controversy_topic_briefs"]))
            warning_count = upsert_warning_interpretations(
                conn,
                ensure_warning_ids(load_csv(files["warning_interpretation"])),
            )
        conn.commit()
    finally:
        conn.close()

    print("Loaded seed data into gemma4good")
    print(f"chemicals={chemical_count}")
    print(f"chemical_aliases={chemical_alias_count}")
    print(f"product_types={product_count}")
    print(f"product_type_aliases={product_alias_count}")
    print(f"regulatory_evidence={regulatory_count}")
    print(f"literature_evidence={literature_count}")
    print(f"controversy_topics={topic_count}")
    print(f"warning_interpretations={warning_count}")


if __name__ == "__main__":
    main()
