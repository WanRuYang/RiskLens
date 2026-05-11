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

The app should expose one chat-style multimodal composer to the user. Within that single intake surface, the user may provide:

- image upload
- direct text entry
- product page link

The system should detect which of these signals are present and normalize the turn into the same payload contract. The user should not have to choose a mode manually.

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

### 4a. Food Exposure Pathway Label Layer

Food products need a more reliable classifier than simple ingredient lookup. The same product can raise different concerns depending on whether the candidate chemical is:

- a declared ingredient or additive
- generated during processing, roasting, frying, smoking, curing, or refining
- a raw-material contaminant
- migrating from food-contact packaging, cookware, or container material

The first ML-ready source for this layer should be California Prop 65 60-day notice data because it links product descriptions to listed chemicals. Those labels should be treated as weak supervision, not final ground truth. The `source` field can teach product/category/process associations, while the `chemicals` field teaches likely concern families.

The classifier target should include:

- `product_category_label`
- `exposure_pathway_label`
- `concern_family_label`
- `chemical_text`
- `label_confidence`
- `label_reason`
- `source_authority` and `jurisdiction` when available

Other warning and regulatory datasets should add source/risk labels such as:

- `warning_or_hazard_listed`
- `restricted_or_thresholded`
- `banned_or_prohibited`
- `allowed_with_conditions`
- `source_context_only`

This lets the app pass compact, structured candidate concerns into Gemma instead of asking Gemma to infer product chemistry from scratch. For example, a chip or roasted coffee product should surface `processing_generated: acrylamide`, while a canned food should surface `food_contact_container: bisphenols` only as a packaging/contact candidate, not as a declared ingredient.

Current implementation:

- weak-label builder: `/Users/adelie/Projects/gemma4good/scripts/build_prop65_label_dataset.py`
- training script: `/Users/adelie/Projects/gemma4good/scripts/train_product_label_classifier.py`
- runtime helper: `/Users/adelie/Projects/gemma4good/product_label_classifier.py`
- model artifact: `/Users/adelie/Projects/gemma4good/models/product_label_classifier/product_label_classifier.joblib`
- model card and metrics: `/Users/adelie/Projects/gemma4good/models/product_label_classifier/MODEL_CARD.md`

The first model is intentionally small: TF-IDF text features plus balanced logistic regression. It should be used as a compact candidate-label/routing layer before database retrieval and Gemma explanation. The runtime helper also applies deterministic chemical-family overrides for obvious chemical names such as lead, acrylamide, formaldehyde, phthalates, PFAS, and bisphenols, because those should not depend only on a learned probability model.

### 5. Answer Layer

The final answer model should only explain the grounded result. It should not invent sources or collapse all evidence types into one kind of warning.

### 5a. Deterministic Risk Formatting Layer

The app should not ask Gemma4 to decide whether broad product classes are toxic. Gemma4 should extract facts and clues, while the risk formatter applies explicit, testable pathway rules.

The current formatter separates:

- direct ingredient or material matches
- likely process-derived compounds
- packaging or food-contact material pathways
- category-based inferred risks
- nutrition/metabolic context that should not be framed as a regulatory chemical warning

Examples now covered by deterministic rules:

- refined vegetable oils, palm oil, canola oil, soybean oil, sunflower oil, and corn oil -> possible glycidyl esters / 3-MCPD esters
- baked, fried, roasted, or coffee products -> possible acrylamide
- smoked, cured, grilled, or processed red meat -> possible PAHs / nitrosamines
- soft plastic, flexible PVC/vinyl, toys, plastic wrap, and food containers -> possible phthalate pathway
- non-stick/PTFE, waterproof/stain-resistant coatings, and grease-resistant food packaging -> possible PFAS/PTFE-related pathway
- composite wood, MDF, particleboard, pressed wood, or wrinkle-free textile clues -> possible formaldehyde pathway
- dyed textile/leather or explicit azo-dye clues -> possible azo dye / aromatic amine pathway
- flame-retardant or treated-foam clues -> possible flame-retardant pathway

False-positive controls are part of the design:

- `corn syrup` is a nutrition/metabolic context, not a direct Prop 65/EPA/EU carcinogen claim.
- `vegetable oil` is not called toxic; it only triggers a possible refined-oil process-contaminant pathway.
- `surfactant` alone is not treated as hazardous; only specific surfactant families trigger specific concerns.
- raw or minimally processed meat should not trigger smoked/cured/grilled process risks unless the product text supports that pathway.

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


### Input interpretation rule

The product should use one chat-style intake surface, but behind the scenes it must still determine the strongest primary signal for the current turn:

- image-driven
- URL-driven
- text-driven

The system should then do one of the following:

- continue if the detected input is sufficient
- ask for better input of the same kind
- recommend the next-best alternate input method

For URL-driven turns specifically, the product should first preview the fetched page text, ingredients, and warnings before moving into category alignment and grounded analysis.

This rule should hold on both macOS and Pixel 8.
