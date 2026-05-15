BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS gemma4good;

SET search_path TO gemma4good, public;

CREATE TABLE IF NOT EXISTS retrieval_documents (
    doc_id BIGSERIAL PRIMARY KEY,
    doc_type TEXT NOT NULL,
    source_authority TEXT,
    source_ref TEXT,
    jurisdiction TEXT,
    chemical_id TEXT REFERENCES chemicals(chemical_id) ON DELETE SET NULL,
    product_type_id TEXT REFERENCES product_types(product_type_id) ON DELETE SET NULL,
    title TEXT,
    body_text TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_retrieval_documents_doc_type
    ON retrieval_documents (doc_type);

CREATE INDEX IF NOT EXISTS idx_retrieval_documents_metadata
    ON retrieval_documents USING gin (metadata);

COMMIT;
