BEGIN;

SET search_path TO gemma4good, public;

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

ALTER TABLE chemical_aliases ADD COLUMN IF NOT EXISTS canonical_id TEXT REFERENCES canonical_substances(canonical_id) ON DELETE SET NULL;
ALTER TABLE chemical_aliases ADD COLUMN IF NOT EXISTS alias TEXT;
ALTER TABLE chemical_aliases ADD COLUMN IF NOT EXISTS source_authority TEXT;
ALTER TABLE chemical_aliases ADD COLUMN IF NOT EXISTS source_name_exact TEXT;
ALTER TABLE chemical_aliases ADD COLUMN IF NOT EXISTS confidence TEXT NOT NULL DEFAULT 'confirmed';
ALTER TABLE chemical_aliases ADD COLUMN IF NOT EXISTS notes TEXT;

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

COMMIT;
