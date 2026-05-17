# gemma4good Local Postgres Scaffold

This folder contains a first-pass PostgreSQL schema and serving-layer code for the `gemma4good` app.

The design goal is:

- keep the authoritative data structured
- support exact and jurisdiction-aware lookups
- support product-category inference from OCR text
- let Gemma 4 consume grounded context instead of guessing

This is intentionally **not** a pure vector-database design.

For this app, the core questions are structured:

- which chemical
- which region
- which source
- listed, warning, restricted, banned, or authorized with conditions
- what threshold or safe-harbor level exists

That means the main database should be PostgreSQL. Vector search can be layered on later for:

- OCR fuzziness
- synonym expansion
- retrieval of longer warning/literature text

## Files

- `schema.sql`: core PostgreSQL schema
- `schema_pgvector_optional.sql`: optional pgvector table for hybrid retrieval
- `service.py`: Python serving helpers for the app/backend
- `load_seed_data.py`: loads normalized seed CSVs
- `load_raw_sources.py`: loads raw source CSVs
- `query_context.py`: local CLI query endpoint for grounded context
- `load_serving_recommendations.py`: loads category-level recommendation rows
- `api.py`: local FastAPI server for the app

## Recommended stack

- PostgreSQL as the source of truth
- optional `pg_trgm` for fuzzy text search
- optional `pgvector` for semantic retrieval
- Gemma 4 as the explanation layer after retrieval

## Layered design

The database should be split into three layers:

### 1. Raw layer

This layer preserves source files as close to the original shape as possible.

- good for traceability
- good for reprocessing when your schema changes
- good for adding new sources later without breaking app queries

Tables:

- `raw_sources`
- `raw_records`
- `ingest_runs`

### 2. Normalized layer

This layer converts raw source rows into stable, queryable entities.

- `chemicals`
- `chemical_aliases`
- `product_types`
- `product_type_aliases`
- `regulatory_evidence`
- `literature_evidence`
- `warning_interpretations`
- `controversy_topics`

### 3. Serving layer

This layer is optimized for fast app queries.

- `product_category_patterns`
- future materialized views for:
  - top chemical signals by category
  - per-region rule summaries
  - chemical summary snapshots

## Core tables

- `chemicals`
- `chemical_aliases`
- `product_types`
- `product_type_aliases`
- `regulatory_evidence`
- `literature_evidence`
- `warning_interpretations`
- `product_category_patterns`
- `query_events`

## Why this fits the app

The app needs to answer questions like:

- "This ingredient appears on the label. Is it on Prop 65?"
- "Is it banned or restricted somewhere else?"
- "Which region says what?"
- "Is the concern from Prop 65, EU, FDA, WHO, IARC, or another source?"
- "What product category does this look like, and what concerns are commonly associated with that category?"

Those are join-heavy, filter-heavy, and source-sensitive queries. PostgreSQL is a much better default than a pure vector database for that workload.

## Suggested first load order

1. `chemical_master.csv` -> `chemicals`
2. `priority_chemical_overrides.csv` -> curated overlay rows for aliases and high-priority gaps
3. `product_risk_mapping.csv` -> `product_types` and `product_type_aliases`
4. `regulatory_evidence.csv` -> `regulatory_evidence`
5. `priority_regulatory_evidence.csv` -> curated overlay rows for high-priority jurisdictional evidence
6. `literature_evidence.csv` -> `literature_evidence`
7. `warning_interpretation.csv` -> `warning_interpretations`
8. category/pattern outputs -> `product_category_patterns`

## Local setup sketch

From the repo root:

```sql
CREATE DATABASE gemma4good;
\c gemma4good
\i database/schema.sql
```

If you have `pgvector` installed, you can also run:

```sql
\i database/schema_pgvector_optional.sql
```

If you are already inside `database/`, use `\i schema.sql` and
`\i schema_pgvector_optional.sql` instead.

## Environment variables for `service.py`

- `GEMMA4GOOD_PG_DSN`
  - example: `postgresql://localhost/gemma4good`
- or standard libpq vars like `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`

## Next implementation step

After the schema is accepted, the next useful step is an ingestion script that maps your existing CSVs directly into these tables.

## Current local query endpoint

You can now query the local database directly:

```bash
python3 database/query_context.py \
  --product-text "waterproof baby bib" \
  --ingredients-text "DEHP; PVC; soft vinyl layer" \
  --warning-text "WARNING: Cancer and Reproductive Harm - www.P65Warnings.ca.gov" \
  --region "California, USA" \
  --pretty
```

This returns grounded JSON with:

- `product_matches`
- `chemical_matches`
- `regulatory_evidence`
- `warning_interpretations`
- `literature_evidence`

This is the retrieval layer that Gemma 4 should read before generating a user-facing explanation.

## Local API

Start the local API from the repo-local database directory:

```bash
cd /Users/adelie/Projects/gemma4good/database
../.venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8010
```

Key endpoints:

- `GET /health`
- `POST /query-context`
- `POST /analyze-product`
- `GET /users/{user_id}/products`
- `GET /users/{user_id}/chemicals`
- `GET /benchmark/image-cases`
- `GET /benchmark/image-cases/{case_id}`
- `GET /review-queue`
- `GET /review-queue/{review_id}`
- `POST /review-queue/{review_id}/corrections`

Example benchmark queries:

```bash
curl "http://127.0.0.1:8010/benchmark/image-cases?segment=food&source_marketplace=Amazon&limit=3"
curl "http://127.0.0.1:8010/benchmark/image-cases/amazon_nonfood_img_035"
```

The benchmark image case endpoints return both stored relative paths and resolved absolute
paths for:

- `front_image_path`
- `ingredients_image_path`
- `warning_image_path`

The intended app flow is:

1. Gemma 4 reads uploaded images and extracts text.
2. The app sends extracted product / ingredient / warning text to `POST /analyze-product`.
3. The API returns:
   - product and category matches
   - matched chemicals
   - regulatory evidence by source and region
   - warning interpretation
   - recommendation bucket
   - user overlap summary for repeated chemicals
4. Gemma 4 then turns that grounded result into the final user-facing explanation.

## vNext feedback loop support

The local API now has explicit support for an agentic review loop.

`POST /analyze-product` can accept these optional fields:

- `input_mode`
  - examples: `image`, `text`, `link`
- `user_corrected_text`
- `user_corrected_category`
- `queue_for_review`
- `review_notes`

The serving layer will auto-generate `review_reasons` when a case looks hard, such as:

- unknown category
- unknown material
- category-level-only evidence with no direct match
- sparse OCR text
- missing priority ingredient information for food or cleaner products

When review is triggered, the API stores a row in `review_queue`. Curated fixes can then be added through
`POST /review-queue/{review_id}/corrections`, which is intended to support:

- benchmark growth
- prompt refinement
- future data curation for OCR/category hard cases
- future targeted fine-tuning if ever needed

Explicit user feedback is also stored in `user_feedback` with a link back to the review case, an
`improvement_status`, and owner-notification metadata. The default owner email is
`wanru.adelie@gmail.com`. Email sending is optional and only occurs when these environment variables
are configured:

- `HAZARDLY_SMTP_HOST`
- `HAZARDLY_SMTP_PORT`
- `HAZARDLY_SMTP_USER`
- `HAZARDLY_SMTP_PASSWORD`
- `HAZARDLY_FEEDBACK_FROM_EMAIL`

Without SMTP configuration, feedback remains safely persisted with `notification_status = 'pending'`
so it can still drive curation or later notification jobs.

## Alias and context normalization

The current schema already supports regulator-specific names without a parallel chemical table:

- aliases and alternate identifiers live in `chemical_aliases`
- jurisdiction-specific meaning lives in `regulatory_evidence`
- material/use phrases on the canonical chemical rows are used as contextual retrieval hints, not as proof that the chemical is present

For example, `Red 40`, `FD&C Red No. 40`, `Allura Red AC`, and `E129` point to the same canonical dye record, while EU and FDA interpretations remain separate evidence rows.
