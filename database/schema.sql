BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS gemma4good;

SET search_path TO gemma4good, public;

CREATE TABLE IF NOT EXISTS raw_sources (
    source_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_category TEXT NOT NULL,
    authority TEXT,
    jurisdiction TEXT,
    file_path TEXT,
    source_url TEXT,
    source_version TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    ingest_run_id BIGSERIAL PRIMARY KEY,
    source_id TEXT REFERENCES raw_sources(source_id) ON DELETE SET NULL,
    ingest_label TEXT,
    file_hash TEXT,
    row_count INTEGER,
    status TEXT NOT NULL DEFAULT 'started',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS raw_records (
    raw_record_id BIGSERIAL PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES raw_sources(source_id) ON DELETE CASCADE,
    ingest_run_id BIGINT REFERENCES ingest_runs(ingest_run_id) ON DELETE SET NULL,
    source_row_number INTEGER,
    natural_key TEXT,
    raw_payload JSONB NOT NULL,
    normalized_name_hint TEXT,
    cas_number_hint TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_id, source_row_number, ingest_run_id)
);

CREATE TABLE IF NOT EXISTS chemicals (
    chemical_id TEXT PRIMARY KEY,
    preferred_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    cas_number TEXT,
    chemical_family TEXT,
    consumer_concern_groups JSONB NOT NULL DEFAULT '[]'::jsonb,
    primary_health_concerns JSONB NOT NULL DEFAULT '[]'::jsonb,
    common_product_types JSONB NOT NULL DEFAULT '[]'::jsonb,
    likely_material_layers JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_priority_level TEXT,
    evidence_summary TEXT,
    ambiguity_notes TEXT,
    seed_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS canonical_substances (
    canonical_id TEXT PRIMARY KEY,
    preferred_name TEXT NOT NULL,
    substance_type TEXT NOT NULL CHECK (
        substance_type IN (
            'single_substance',
            'polymer',
            'mixture',
            'regulatory_group',
            'contaminant_class',
            'route_scoped_substance'
        )
    ),
    chemical_family TEXT,
    cas_numbers TEXT[],
    inchi_key TEXT,
    parent_canonical_id TEXT REFERENCES canonical_substances(canonical_id) ON DELETE SET NULL,
    risk_summary TEXT,
    retrieval_notes TEXT,
    legacy_chemical_id TEXT REFERENCES chemicals(chemical_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chemical_aliases (
    alias_id BIGSERIAL PRIMARY KEY,
    chemical_id TEXT NOT NULL REFERENCES chemicals(chemical_id) ON DELETE CASCADE,
    canonical_id TEXT REFERENCES canonical_substances(canonical_id) ON DELETE SET NULL,
    alias_text TEXT NOT NULL,
    alias TEXT,
    normalized_alias TEXT NOT NULL,
    alias_type TEXT NOT NULL DEFAULT 'synonym',
    source_authority TEXT,
    source_name_exact TEXT,
    confidence TEXT NOT NULL DEFAULT 'confirmed',
    notes TEXT,
    source_label TEXT,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (chemical_id, normalized_alias)
);

CREATE TABLE IF NOT EXISTS regulatory_entries (
    regulatory_entry_id TEXT PRIMARY KEY,
    canonical_id TEXT NOT NULL REFERENCES canonical_substances(canonical_id) ON DELETE CASCADE,
    source_authority TEXT NOT NULL CHECK (
        source_authority IN ('FDA', 'EPA', 'EU', 'EFSA', 'ECHA', 'WHO', 'JECFA', 'IARC', 'Prop65', 'Codex')
    ),
    jurisdiction TEXT,
    source_name_exact TEXT,
    regulatory_status TEXT NOT NULL,
    route_context TEXT NOT NULL,
    effective_date DATE,
    hazard_basis TEXT,
    limit_value TEXT,
    citation_url TEXT,
    summary_for_model TEXT,
    warning_for_model TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS substance_relationships (
    subject_canonical_id TEXT NOT NULL REFERENCES canonical_substances(canonical_id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL CHECK (
        relation_type IN (
            'salt_of',
            'parent_of',
            'member_of',
            'related_compound_of',
            'precursor_of',
            'degradation_product_of',
            'polymer_of',
            'monomer_of',
            'commonly_confused_with',
            'route_scope_of'
        )
    ),
    object_canonical_id TEXT NOT NULL REFERENCES canonical_substances(canonical_id) ON DELETE CASCADE,
    confidence TEXT NOT NULL,
    notes TEXT,
    PRIMARY KEY (subject_canonical_id, relation_type, object_canonical_id)
);

CREATE TABLE IF NOT EXISTS product_types (
    product_type_id TEXT PRIMARY KEY,
    normalized_product_type TEXT NOT NULL,
    mapped_product_category TEXT NOT NULL,
    likely_material_layers JSONB NOT NULL DEFAULT '[]'::jsonb,
    high_priority_concern_groups JSONB NOT NULL DEFAULT '[]'::jsonb,
    likely_regulatory_datasets JSONB NOT NULL DEFAULT '[]'::jsonb,
    warning_guidance_short TEXT,
    what_to_ask_or_scan_next TEXT,
    priority_level TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS product_type_aliases (
    alias_id BIGSERIAL PRIMARY KEY,
    product_type_id TEXT NOT NULL REFERENCES product_types(product_type_id) ON DELETE CASCADE,
    alias_text TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    alias_source TEXT NOT NULL DEFAULT 'consumer_alias',
    UNIQUE (product_type_id, normalized_alias)
);

CREATE TABLE IF NOT EXISTS regulatory_evidence (
    evidence_id TEXT PRIMARY KEY,
    chemical_id TEXT REFERENCES chemicals(chemical_id) ON DELETE SET NULL,
    preferred_name TEXT NOT NULL,
    normalized_preferred_name TEXT NOT NULL,
    source_dataset_id TEXT,
    source_authority TEXT NOT NULL,
    source_type TEXT,
    country_or_jurisdiction TEXT,
    region_label TEXT,
    product_category TEXT,
    product_scope TEXT,
    regulation_or_list_name TEXT NOT NULL,
    regulatory_status TEXT NOT NULL,
    hazard_basis TEXT,
    warning_flag BOOLEAN NOT NULL DEFAULT FALSE,
    ban_flag BOOLEAN NOT NULL DEFAULT FALSE,
    restriction_flag BOOLEAN NOT NULL DEFAULT FALSE,
    allowed_flag BOOLEAN NOT NULL DEFAULT FALSE,
    hazard_classification_flag BOOLEAN NOT NULL DEFAULT FALSE,
    threshold_value TEXT,
    threshold_unit TEXT,
    threshold_type TEXT,
    threshold_conditions TEXT,
    safe_harbor_or_adi TEXT,
    safe_harbor_or_adi_unit TEXT,
    citation_url TEXT,
    citation_title TEXT,
    citation_publisher TEXT,
    source_row_reference TEXT,
    evidence_type TEXT,
    consumer_concern_groups JSONB NOT NULL DEFAULT '[]'::jsonb,
    year_added TEXT,
    date_added TEXT,
    listing_mechanism TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS literature_evidence (
    literature_id TEXT PRIMARY KEY,
    topic_id TEXT,
    topic_name TEXT NOT NULL,
    chemical_or_material_scope TEXT,
    evidence_role TEXT,
    evidence_type TEXT,
    evidence_strength TEXT,
    stance_direction TEXT,
    jurisdiction_or_body TEXT,
    consumer_context TEXT,
    claim_summary TEXT,
    important_limitations TEXT,
    citation_title TEXT,
    citation_url TEXT,
    publisher_or_journal TEXT,
    publication_year TEXT,
    source_type TEXT,
    recommended_for_consumer_quote BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS controversy_topics (
    topic_id TEXT PRIMARY KEY,
    topic_name TEXT NOT NULL,
    consumer_question TEXT,
    why_controversial TEXT,
    what_regulation_says TEXT,
    what_literature_says TEXT,
    how_gemma_should_frame_it TEXT,
    priority_level TEXT,
    primary_source_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS warning_interpretations (
    warning_id TEXT PRIMARY KEY,
    regime TEXT NOT NULL,
    warning_text_pattern TEXT NOT NULL,
    normalized_warning_text_pattern TEXT NOT NULL,
    product_context TEXT,
    concern_level_default TEXT,
    what_it_legally_means TEXT,
    what_it_does_not_mean TEXT,
    when_to_take_more_seriously TEXT,
    when_not_to_overinterpret TEXT,
    suggested_user_action TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS product_category_patterns (
    pattern_id BIGSERIAL PRIMARY KEY,
    product_use_category TEXT NOT NULL,
    material_subcategory TEXT,
    product_archetype TEXT,
    category_l1 TEXT,
    category_l2 TEXT,
    chemical_id TEXT REFERENCES chemicals(chemical_id) ON DELETE SET NULL,
    chemical_name TEXT,
    chemical_family TEXT,
    evidence_strength TEXT,
    concern_level TEXT,
    unique_notices INTEGER,
    notice_rows INTEGER,
    first_seen_date DATE,
    last_seen_date DATE,
    example_products TEXT,
    recommendation_context TEXT,
    recommended_caution_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS serving_recommendations (
    recommendation_id BIGSERIAL PRIMARY KEY,
    product_use_category TEXT NOT NULL,
    material_subcategory TEXT NOT NULL,
    coating_or_decoration_signal TEXT,
    food_contact_signal TEXT,
    child_use_signal TEXT,
    heating_use_signal TEXT,
    inhalation_signal TEXT,
    total_unique_notices INTEGER,
    total_notice_rows INTEGER,
    top_chemical_families TEXT,
    top_chemicals TEXT,
    example_products TEXT,
    recommendation_priority TEXT,
    recommended_caution_text TEXT,
    why_this_matters TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_products (
    user_product_id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    product_name TEXT,
    product_page_url TEXT,
    raw_ocr_text TEXT,
    extracted_ingredient_text TEXT,
    extracted_warning_text TEXT,
    region_label TEXT,
    matched_product_type_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    matched_categories JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommendation_bucket TEXT,
    recommendation_summary TEXT,
    concern_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_analysis_payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS user_product_chemicals (
    user_product_chemical_id BIGSERIAL PRIMARY KEY,
    user_product_id BIGINT NOT NULL REFERENCES user_products(user_product_id) ON DELETE CASCADE,
    chemical_id TEXT REFERENCES chemicals(chemical_id) ON DELETE SET NULL,
    preferred_name TEXT NOT NULL,
    source_authority TEXT,
    country_or_jurisdiction TEXT,
    regulatory_status TEXT,
    hazard_basis TEXT,
    matched_from TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS query_events (
    query_id BIGSERIAL PRIMARY KEY,
    user_id TEXT,
    session_id TEXT,
    query_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    region_label TEXT,
    product_page_url TEXT,
    raw_ocr_text TEXT,
    product_text TEXT,
    ingredient_text TEXT,
    warning_text TEXT,
    matched_product_type_id TEXT REFERENCES product_types(product_type_id) ON DELETE SET NULL,
    matched_chemical_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    matched_evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS review_queue (
    review_id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT NOT NULL DEFAULT 'normal',
    source_flow TEXT,
    user_id TEXT,
    session_id TEXT,
    user_product_id BIGINT REFERENCES user_products(user_product_id) ON DELETE SET NULL,
    input_mode TEXT,
    product_name TEXT,
    product_page_url TEXT,
    region_label TEXT,
    raw_ocr_text TEXT,
    extracted_ingredient_text TEXT,
    extracted_warning_text TEXT,
    inferred_product_use_category TEXT,
    inferred_material_subcategory TEXT,
    recommendation_bucket TEXT,
    review_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    review_notes TEXT,
    review_payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS curated_corrections (
    correction_id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    review_id BIGINT REFERENCES review_queue(review_id) ON DELETE CASCADE,
    correction_type TEXT NOT NULL,
    original_value TEXT,
    corrected_value TEXT NOT NULL,
    reviewer_notes TEXT,
    approved BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS user_feedback (
    feedback_id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    review_id BIGINT REFERENCES review_queue(review_id) ON DELETE SET NULL,
    user_id TEXT,
    session_id TEXT,
    product_name TEXT,
    input_mode TEXT,
    feedback_text TEXT NOT NULL,
    feedback_kind TEXT NOT NULL DEFAULT 'correction',
    owner_email TEXT NOT NULL DEFAULT 'wanru.adelie@gmail.com',
    notification_status TEXT NOT NULL DEFAULT 'pending',
    notification_error TEXT,
    notification_sent_at TIMESTAMPTZ,
    improvement_status TEXT NOT NULL DEFAULT 'queued',
    converted_to_correction_id BIGINT REFERENCES curated_corrections(correction_id) ON DELETE SET NULL,
    feedback_payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

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

CREATE INDEX IF NOT EXISTS idx_chemicals_normalized_name_md5
    ON chemicals ((md5(normalized_name)));

CREATE INDEX IF NOT EXISTS idx_chemicals_preferred_name_trgm
    ON chemicals USING gin (preferred_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_chemical_aliases_normalized_alias
    ON chemical_aliases (normalized_alias);

CREATE INDEX IF NOT EXISTS idx_chemical_aliases_alias_trgm
    ON chemical_aliases USING gin (alias_text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_canonical_substances_family
    ON canonical_substances (chemical_family);

CREATE INDEX IF NOT EXISTS idx_chemical_aliases_canonical_id
    ON chemical_aliases (canonical_id);

CREATE INDEX IF NOT EXISTS idx_regulatory_entries_canonical_id
    ON regulatory_entries (canonical_id);

CREATE INDEX IF NOT EXISTS idx_regulatory_entries_authority_status
    ON regulatory_entries (source_authority, regulatory_status);

CREATE INDEX IF NOT EXISTS idx_substance_relationships_subject
    ON substance_relationships (subject_canonical_id);

CREATE INDEX IF NOT EXISTS idx_substance_relationships_object
    ON substance_relationships (object_canonical_id);

CREATE INDEX IF NOT EXISTS idx_raw_records_source_id
    ON raw_records (source_id);

CREATE INDEX IF NOT EXISTS idx_raw_records_ingest_run_id
    ON raw_records (ingest_run_id);

CREATE INDEX IF NOT EXISTS idx_raw_records_payload
    ON raw_records USING gin (raw_payload);

CREATE INDEX IF NOT EXISTS idx_product_types_normalized_product_type
    ON product_types (normalized_product_type);

CREATE INDEX IF NOT EXISTS idx_product_type_aliases_normalized_alias
    ON product_type_aliases (normalized_alias);

CREATE INDEX IF NOT EXISTS idx_product_type_aliases_alias_trgm
    ON product_type_aliases USING gin (alias_text gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_regulatory_evidence_normalized_preferred_name_md5
    ON regulatory_evidence ((md5(normalized_preferred_name)));

CREATE INDEX IF NOT EXISTS idx_regulatory_evidence_authority_status
    ON regulatory_evidence (source_authority, regulatory_status);

CREATE INDEX IF NOT EXISTS idx_regulatory_evidence_jurisdiction
    ON regulatory_evidence (country_or_jurisdiction, region_label);

CREATE INDEX IF NOT EXISTS idx_regulatory_evidence_product_category
    ON regulatory_evidence (product_category);

CREATE INDEX IF NOT EXISTS idx_regulatory_evidence_preferred_name_trgm
    ON regulatory_evidence USING gin (preferred_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_warning_interpretations_pattern_trgm
    ON warning_interpretations USING gin (warning_text_pattern gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_serving_recommendations_category
    ON serving_recommendations (product_use_category, material_subcategory);

CREATE INDEX IF NOT EXISTS idx_user_products_user_id
    ON user_products (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_product_chemicals_user_product_id
    ON user_product_chemicals (user_product_id);

CREATE INDEX IF NOT EXISTS idx_user_product_chemicals_chemical_id
    ON user_product_chemicals (chemical_id);

CREATE INDEX IF NOT EXISTS idx_benchmark_image_cases_segment
    ON benchmark_image_cases (segment, category_group);

CREATE INDEX IF NOT EXISTS idx_review_queue_status_created_at
    ON review_queue (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_review_queue_user_id_created_at
    ON review_queue (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_feedback_status_created_at
    ON user_feedback (improvement_status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_feedback_review_id
    ON user_feedback (review_id);

COMMIT;
