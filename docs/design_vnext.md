# vNext Design

## Goal

The goal is not to preserve the first app structure. The goal is to converge on a better design using the benchmark evidence we now have.

The strongest current direction is:

- agentic user experience
- linear, benchmarkable reasoning core
- explicit category and material schema
- grounded retrieval before final explanation
- review-queue support for hard cases and future self-improvement

## Recommended Architecture

### 1. Input Layer

The app should support three entry modes:

- image upload
- direct text entry
- product page link

These should all converge into the same normalized payload.

### 2. Extraction Layer

For image input:

- OCR text extraction
- OCR structuring into product name, ingredient text, warning text, and caution text

For direct text input:

- skip OCR and normalize directly into the same payload shape

For product links:

- use the link as supporting category or brand context only
- do not treat the link as proof of exact ingredients or materials

### 3. Interpretation Layer

This layer should always produce:

- `product_use_category`
- `material_or_form`
- `information_priority`
- `confidence_notes`

This is where the category reference and material reference should be applied.

### 4. Grounded Retrieval Layer

The local API and Postgres database should be treated as the source of truth for:

- product and ingredient matching
- source typing
- region or jurisdiction typing
- warning vs restriction vs ban vs allowed-with-conditions
- recommendation bucket policy
- user history overlap

### 5. Answer Layer

The final answer model should only explain the grounded result. It should not invent sources or collapse all evidence types into one kind of warning.

### 6. Agentic Interaction Layer

The product should remain agentic from the user perspective, but the agentic flow should be thin and state-driven.

Recommended states:

1. intake
2. OCR confirm if needed
3. category confirm if needed
4. retrieval
5. grounded answer
6. feedback and follow-up

The agentic layer is useful because it enables:

- user trust
- correction of OCR and category mistakes
- explicit inspection of what the system used
- storage of hard cases for future improvement

## Why This Is Better Than v1

This design is better than the original app flow because:

- it keeps the product transparent without making the backend overly branchy
- it aligns with the benchmark path that actually improved performance
- it makes Stage 1 and Stage 2 evaluation cleaner
- it supports future mobile deployment with the same fixed Gemma model size
- it creates a structured path for self-improvement through hard-case storage

## Review Queue Design

The database now supports a review queue for hard cases.

A case should be queued when one or more of the following are true:

- OCR had to be corrected by the user
- category had to be overridden by the user
- product category is unknown
- material is unknown
- only category-level evidence exists with no direct chemical match
- OCR text is sparse or low quality
- the priority information for the category is missing

This queue should be used for:

- benchmark expansion
- prompt refinement
- new rule design
- curated correction datasets
- future targeted fine-tuning if warranted later

## Current Known Weak Areas

Based on the latest benchmark and coverage scan, the remaining weak areas are:

- food-contact ceramic plus lead source framing
- sports and hydration product titles
- clothing and wearables material resolution
- kitchen-home accessory material resolution

These should be improved through retrieval and schema design first, not by changing model size.


## Platform portability

The vNext design should be treated as a cross-platform core with two shells:

- macOS development shell: Python + Gradio + local API
- Pixel 8 product shell: native Android client using the same normalized payload and retrieval contract

This means the product logic should stay inside:

- the normalized payload contract
- the grounded retrieval contract
- the benchmarked Stage 2 schema
- the review-queue logic

The UI shell may change, but those contracts should not.


## Android contract mirror

The Pixel 8 client should not infer the backend shape ad hoc. Android mirror models should be generated or maintained from the same contract boundary.

Current mirror artifacts:

- `android_contract/Gemma4GoodApiModels.kt`
- `docs/android_contract_mapping.md`


### Input-mode control rule

The product should not mix multiple primary intake methods in one step. The user should choose one primary mode:

- image
- URL
- text

The system should then do one of the following:

- continue if the mode is sufficient
- ask for better input within that mode
- recommend the next-best alternate mode

This rule should hold on both macOS and Pixel 8.
