# gemma4good

A local, evidence-grounded consumer safety assistant built around a fixed-size Gemma 4 model.

RiskLens uses Gemma 4 as the multimodal model backend. Gemma 4 is subject to its own license and acceptable use terms. This project does not provide medical, legal, or regulatory advice; it provides evidence-grounded product risk summaries for informational purposes only.

## Project stance

`Gemma 4` is the intended product model.

`OpenAI` is used only for:

- benchmark judging
- reference comparisons
- methodology validation

It is **not** the intended production model for the mobile app.

## Current recommended architecture

The recommended direction is:

- single-purpose product-analysis user experience
- linear, benchmarkable core pipeline
- grounded retrieval through the local API
- compact product-label classifier for category/pathway/concern routing
- explicit category and material reasoning
- review-queue capture for hard OCR and category cases

This means:

1. accept one multimodal product-analysis turn at a time, then auto-detect whether the user provided images, a URL, or typed product text
2. if that mode is insufficient, recommend a better method instead of forcing a weak answer
3. extract or normalize text into one shared payload
4. confirm OCR or category only when needed
5. call the local API for grounded retrieval
6. generate the final answer with Gemma 4
7. store hard cases for future review and improvement

Supporting design docs:

- [/Users/adelie/Projects/gemma4good/docs/design_vnext.md](/Users/adelie/Projects/gemma4good/docs/design_vnext.md)
- [/Users/adelie/Projects/gemma4good/docs/test_plan_vnext.md](/Users/adelie/Projects/gemma4good/docs/test_plan_vnext.md)
- [/Users/adelie/Projects/gemma4good/docs/platform_targets.md](/Users/adelie/Projects/gemma4good/docs/platform_targets.md)
- [/Users/adelie/Projects/gemma4good/docs/pixel8_client_plan.md](/Users/adelie/Projects/gemma4good/docs/pixel8_client_plan.md)
- [/Users/adelie/Projects/gemma4good/docs/android_contract_mapping.md](/Users/adelie/Projects/gemma4good/docs/android_contract_mapping.md)
- [/Users/adelie/Projects/gemma4good/docs/run_on_pixel8.md](/Users/adelie/Projects/gemma4good/docs/run_on_pixel8.md)
- [/Users/adelie/Projects/gemma4good/docs/demo_plan.md](/Users/adelie/Projects/gemma4good/docs/demo_plan.md)
- [/Users/adelie/Projects/gemma4good/docs/risklens_score.md](/Users/adelie/Projects/gemma4good/docs/risklens_score.md)

## Repo structure

```text
RiskLens/
├── app.py                      # Main Gradio application
├── app_shared.py               # Shared logic and API client
├── app_openai.py               # OpenAI reference evaluation app
├── mlx_engine.py               # MLX-VLM model interface & agents
├── risklens_score.py           # Core A-E scoring logic
├── safety_lookup.py            # Local RAG knowledge base interface
├── database_manager.py         # SQLite product cache & history
├── product_risk_formatter.py   # Signal calibration & explanation
├── browser_fetcher.py          # Playwright-based web extractor
├── search_fetcher.py           # Web search fallback
├── platform_profiles.py        # Hardware-specific configurations
├── ui_components.py            # Gradio UI rendering helpers
├── benchmarks/                 # Performance & accuracy benchmarks
│   ├── benchmark_cases.json
│   ├── run_mlx_benchmarks.py
│   └── benchmark_images/       # Gold-standard test images
├── scripts/
│   ├── build/                  # Dataset & knowledge base builders
│   ├── setup.sh                # Environment setup script
│   └── start_app.sh            # Production launch script
├── database/                   # Local API & Postgres retrieval layer
│   ├── api.py                  # FastAPI endpoint
│   └── service.py              # SQL retrieval logic
├── android_client/             # Native Android shell (Pixel 8)
├── android_contract/           # Shared Kotlin API models
├── tests/
│   └── integration/            # Full-pipeline integration tests
├── tools/
│   └── debug/                  # Diagnostic & development tools
├── prompts/                    # System prompts & category reference
├── docs/                       # Technical & architectural docs
├── models/                     # Local model weights & classifiers
├── data/                       # Regulatory & chemical databases
└── outputs/                    # Logs and analysis history
```

## Production path vs evaluation path

### Production-oriented path

- [app.py](/Users/adelie/Projects/gemma4good/app.py)
- [app_shared.py](/Users/adelie/Projects/gemma4good/app_shared.py)
- [vnext_contract.py](/Users/adelie/Projects/gemma4good/vnext_contract.py)
- [product_label_classifier.py](/Users/adelie/Projects/gemma4good/product_label_classifier.py)
- [risklens_score.py](/Users/adelie/Projects/gemma4good/risklens_score.py)
- local FastAPI + Postgres retrieval layer
- category and material reasoning
- user history and hard-case review queue
- UI-rendered RiskLens Score bar for chemical/material/process exposure signals
- separate non-scoring food notes for nutrition context such as high added sugar, high sodium, and high saturated fat
- evidence-weighted RiskLens Score: each score-relevant signal is weighted by severity, evidence strength, exposure likelihood, route relevance, and population context instead of simple keyword matching

### Evaluation-only path

- [app_openai.py](/Users/adelie/Projects/gemma4good/app_openai.py)
- [run_openai_pretest.py](/Users/adelie/Projects/gemma4good/run_openai_pretest.py)
- OpenAI-judged OCR benchmark
- OpenAI reference comparisons in Stage 2

Use this path only to evaluate Gemma 4 and the system design. Do not treat it as the intended deployment path.

---

## Version History (M4 Mac Optimization)

| Version | Milestone | Description |
| :--- | :--- | :--- |
| **v1.0** | MLX Migration | Initial port from Transformers to MLX-VLM. 10x faster startup. |
| **v3.3** | Vision Peak | Breakthrough 83.3% recall using Contextual Tiling and Native Hybrid OCR. |
| **v8.0** | Native Search | Eliminated external API dependencies for maximum granularity. |
| **v21.0** | Semantic Store | Integrated local vector store with 9,133 forensic samples for Dynamic Few-Shot RAG. |
| **v22.0** | Parallel Vision| Leveraged M4 multi-core CPU for concurrent multi-image preprocessing. |
| **v25.0** | Universal | Universal OCR Bridge for cross-platform parity (Pixel 8 ready). |
| **v26.0** | **Forensic Peak**| **Forensic Drift Auditing (Physical vs. Digital transparency audit).** |

---

## Core Capabilities (v26.0)

1.  **Ultimate Forensic Vision**: Tri-modal fusion (Native macOS Vision + Adaptive Optical Tiling + VLM Semantic Context).
2.  **Autonomous Intelligence**: Dynamic Few-Shot RAG referencing a massive 9,000+ sample safety archive.
3.  **Cross-Audit Logic**: Forensic Drift Auditor compares physical packaging against digital retailer descriptions.
4.  **Hardware Mastery**: Optimized for Apple M4 multi-core CPU and Unified Memory (66.1 TPS).
5.  **Universal Design**: Cross-platform OCR abstraction ready for mobile deployment.

---

## Quick Start (M4 Mac)

### Gemma product path

Start the local retrieval API first:

```bash
cd /Users/adelie/Projects/gemma4good/database
../.venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8010
```

Then start the macOS Gradio app in a second terminal:

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python app.py
```

### OpenAI reference path

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python app_openai.py
```

Again, the OpenAI path is for evaluation and reference only.

## Current web app flow

The current macOS/web app is a single-purpose product-analysis tool rather than a general chatbot. The user provides one product case through one multimodal input area and clicks `Analyze Product`.

Supported input types:

- typed product text, pasted ingredients, or pasted nutrition facts
- product URLs
- up to 5 images, such as the front label, ingredient panel, Nutrition Facts panel, warning sticker, or phone-camera photos

Before analysis, the app:

1. detects whether the case started from image, URL, or text
2. tries to collect product name, category, ingredients/materials, Nutrition Facts, claims, and warning text
3. checks whether the information is complete enough for a full product-specific analysis
4. asks for missing label evidence when the page or image only provides a product name or marketing text
5. sends one normalized payload to the local API for retrieval and Gemma 4 reasoning

URL handling is best-effort. The app normalizes retailer links where possible, fetches readable product-page context when available, and falls back to asking for label images or pasted text when a retailer blocks automated access or hides key details behind dynamic page controls.

## Visual Design System

RiskLens uses a clean, light-themed visual identity designed for consumer trust and scientific credibility.

- **Primary Brand Color:** Deep Science Blue (#1E5A7A). Used for headers, primary buttons, and key interface highlights.
- **Background:** Very light blue-gray (#F7FAFC). Provides a calm, professional canvas that reduces eye strain and emphasizes information hierarchy.
- **Score Semantic Mapping:**
    - **Grade A (Green):** Low concern.
    - **Grade B (Teal):** Minor concern.
    - **Grade C (Amber):** Moderate concern.
    - **Grade D (Orange):** High concern.
    - **Grade E (Red):** Very high concern.
- **Flag Categorization (Soft Chips):**
    - **Chemical / Process (Amber):** Signals related to substances or processing methods.
    - **Regulatory / Material (Orange):** Confirmed hazardous ingredients or high-priority watchlists.
    - **Nutrition (Blue):** Supplemental dietary context (High sugar, etc.).
    - **Allergen (Lavender):** Informational allergen warnings.
    - **Ingredient / General (Gray):** Non-scoring ingredient notes.

This light-first design system ensures that RiskLens feels like a professional safety assistant rather than a developer dashboard, prioritized for readability and accessibility.

Both clients now follow the same conceptual sequence:

1. Product identification
2. OCR / label extraction
3. Ingredient and Nutrition Facts parsing
4. Chemical and process-risk screening
5. Nutrition-flag derivation
6. RiskLens Score generation
7. RiskLens Flags rendering
8. Result explanation, input composer, and optional feedback submission

The normalized payload and API response are shared across clients. In particular, both clients render from the backend-owned `risklens_score.score`, `risklens_score.total_risk_points`, and typed `risklens_score.flags` list so the score and flag semantics stay aligned. RiskLens uses a weighted evidence model rather than a simple keyword/list-match penalty; nutrition/allergen/note flags are display-only and do not change the A-E score. A final grade guardrail prevents `A` whenever any score-relevant chemical/process/regulatory/material flag has positive risk points.

For image input, the identify path is intentionally two-stage: Gemma first produces literal OCR transcripts for every uploaded image, then Gemma reads the combined transcript to separate product identity, ingredients, Nutrition Facts, and warnings before category inference, risk screening, or database retrieval runs.

## Current web output

The web result view now uses this order:

1. Input composer
2. `Analyze Product` / `Start new analysis` actions
3. **RiskLens Score** A-E bar
4. **RiskLens Flags** card with separate rows for chemical/process signals, nutrition notes, allergen notes, and ingredient notes
5. **Product Info** at the top of the report
6. Compact scrollable **Result explanation** panel
7. Disclaimer
8. **Submit feedback** control with short correction guidance

The web UI no longer renders a second nutrition score card. This keeps chemical-exposure screening separate from general nutrition quality while still showing useful food-label context.

The visible report keeps product identity and extracted evidence readable:

- product name and category are shown for all supported input types
- OCR placeholders such as `NO READABLE TEXT` are suppressed in the user-facing Product Info section
- missing ingredients or Nutrition Facts are reported as missing rather than displayed as noisy OCR artifacts

## Scope Guard and Misuse Prevention

The live demo is intentionally limited to product safety analysis. Before generating a report, RiskLens applies a quick local misuse pre-filter and then uses Gemma for the formal scope classification when the turn is not already obvious. The turn is classified as in-scope product safety input, out-of-scope input, or unclear input that still needs product-label evidence.

- Off-topic requests are refused with one fixed redirect message.
- Unclear requests ask for a product image, label text, ingredient list, nutrition facts, or packaging warning.
- The app is designed as a single-purpose product-analysis tool, not a general chatbot.
- The web demo does not keep conversational memory between analyses.
- This reduces misuse risk and avoids spending unnecessary inference on unrelated prompts.

## Phone App Design

The Android phone app uses **Android ML Kit Text Recognition** as its OCR/input extraction layer for camera or photo-gallery images.

The intended phone flow is:

```text
Camera / Product Image
-> Android ML Kit OCR
-> OCR normalization into shared product fields
-> Gemma 4 identify + safety reasoning
-> Grounded retrieval and Product Safety Report
```

ML Kit is used only to convert visible label text into machine-readable text. It does not perform risk scoring, safety reasoning, regulatory interpretation, or report generation.

Gemma 4 remains the core reasoning engine. After OCR, the phone app sends the noisy text through the same normalized payload boundary used by the web app so Gemma 4 can identify the product, clean and validate ingredients, infer category and processing clues, preserve nutrition facts, and support the downstream safety analysis.

Current Android implementation note: the app now performs on-device ML Kit OCR, then calls the local `/identify-product` endpoint so Gemma 4 can structure the OCR into the shared product fields before `/analyze-product` runs. The Android client also mirrors the RiskLens Score plus food-flag presentation used by the web app. The Python app remains the reference implementation while the phone shell continues to converge on the same report behavior.

## Web App vs Phone App

### Web app

- User enters product information manually, pastes a URL, or uploads product text/images.
- Product identification starts from user-provided or Gemma-extracted text.
- The safety agent analyzes the normalized structured product data and produces the grounded report.

### Phone app

- Image capture or gallery upload is the first step in the identify flow.
- Android ML Kit OCR extracts visible product-label text from the image.
- OCR output is normalized into the same structured product input format.
- The same Gemma 4 product-identification and safety-analysis pipeline is reused after OCR.
- The result screen uses stacked mobile cards in the same order as web: input composer, Analyze Product / Start new analysis actions, RiskLens Score, RiskLens Flags, Product Info inside the report, scrollable Result explanation, disclaimer, and Submit feedback.

## Nutrition flag policy

Food-only flags are separate from the RiskLens Score.

## Shared Material and Additive Evidence

Web and Android clients use the same backend-owned retrieval and scoring path. The app now keeps high-priority cross-jurisdiction names in a curated data overlay instead of hard-coding every alias in prompt logic:

- `data/app_data/priority_chemical_overrides.csv`
- `data/app_data/priority_regulatory_evidence.csv`

This overlay feeds the same canonical tables used by the app:

- `chemicals`
- `chemical_aliases`
- `regulatory_evidence`

The normalized model intentionally separates:

- confirmed ingredient or material
- intentionally added additive
- possible migration chemical
- possible contamination signal
- legacy manufacturing or processing chemical
- regulatory listing
- product-specific evidence
- category-level evidence only

RiskLens treats `regulated` as context, not as a synonym for `dangerous`. Likewise, a `permitted additive` is not assumed to have zero risk, a `possible contaminant` is not presented as a confirmed ingredient, and a `Prop 65` listing is not treated as proof that a specific product is unsafe. Recommendations are conditioned on material, use context, route, jurisdiction, and confidence.

Synthetic dyes use the same data path. For example, `Allura Red AC`, `FD&C Red No. 40`, `Red 40`, `E129`, and `CI 16035` are aliases for the same canonical dye record, so U.S. and EU source names can be reconciled before explanation.

- `High added sugar` is derived from sugar/added-sugar evidence in the available label text.
- `High saturated fat` is derived from saturated-fat or relevant fat/oil evidence.
- `High sodium` now requires a Nutrition Facts threshold rather than the word `sodium` alone: at least `20% DV` or about `460 mg` per serving. This avoids false positives on low-sodium labels such as `85 mg / 4% DV`.
- Common allergens are no longer shown as a general warning by default; they should remain informational unless the user requests allergen screening or provides an allergy profile.

## Platform targets

The current repo intentionally separates:

- `mac_dev`: Python + Gradio + local FastAPI/Postgres for development, debugging, and benchmark runs
- `pixel8_android`: future native Android shell using the same normalized payload, retrieval contract, and review-queue design

Platform notes are documented in:

- [/Users/adelie/Projects/gemma4good/platform_profiles.py](/Users/adelie/Projects/gemma4good/platform_profiles.py)
- [/Users/adelie/Projects/gemma4good/docs/platform_targets.md](/Users/adelie/Projects/gemma4good/docs/platform_targets.md)

This is how we keep the product runnable on macOS today while keeping the core logic portable to Pixel 8 later.

Android-side contract models are now defined in:

- [/Users/adelie/Projects/gemma4good/android_contract/Gemma4GoodApiModels.kt](/Users/adelie/Projects/gemma4good/android_contract/Gemma4GoodApiModels.kt)
- [/Users/adelie/Projects/gemma4good/android_contract/Gemma4GoodApiService.kt](/Users/adelie/Projects/gemma4good/android_contract/Gemma4GoodApiService.kt)
- [/Users/adelie/Projects/gemma4good/android_contract/Gemma4GoodContractAdapters.kt](/Users/adelie/Projects/gemma4good/android_contract/Gemma4GoodContractAdapters.kt)
- [/Users/adelie/Projects/gemma4good/android_contract/RetrofitUsageExample.md](/Users/adelie/Projects/gemma4good/android_contract/RetrofitUsageExample.md)
- [/Users/adelie/Projects/gemma4good/android_contract/README.md](/Users/adelie/Projects/gemma4good/android_contract/README.md)

A minimal Android Studio client shell is also included at:

- [/Users/adelie/Projects/gemma4good/android_client/README.md](/Users/adelie/Projects/gemma4good/android_client/README.md)
- Pixel run guide: [/Users/adelie/Projects/gemma4good/docs/run_on_pixel8.md](/Users/adelie/Projects/gemma4good/docs/run_on_pixel8.md)

## End-to-end app tests

### Gemma path

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python test_app_flow.py
```

Outputs:

- `outputs/app_flow_test/final_report.md`
- `outputs/app_flow_test/debug_payload.json`

### OpenAI reference path

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python test_app_flow_openai.py
```

Outputs:

- `outputs/app_flow_test_openai/final_report.md`
- `outputs/app_flow_test_openai/debug_payload.json`

## Product label classifier

The product-label layer turns Prop 65 notice/product associations and regulatory source tables into compact candidate labels before Gemma writes the final answer. It predicts product category, exposure pathway, concern family, and regulatory risk label.

Build weak labels:

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python scripts/build_prop65_label_dataset.py
```

Train the classifier:

```bash
python scripts/train_product_label_classifier.py
```

Current model outputs:

- Model card: `/Users/adelie/Projects/gemma4good/models/product_label_classifier/MODEL_CARD.md`
- Model artifact: `/Users/adelie/Projects/gemma4good/models/product_label_classifier/product_label_classifier.joblib`
- Metrics JSON: `/Users/adelie/Projects/gemma4good/models/product_label_classifier/metrics_summary.json`
- Product-to-chemical linkage index: `/Users/adelie/Projects/gemma4good/data/derived/label_datasets/product_chemical_linkage.json`

Current held-out weak-label scores:

| Task | Accuracy | Macro F1 |
| --- | ---: | ---: |
| product_category | 0.9721 | 0.9616 |
| exposure_pathway | 0.9658 | 0.7986 |
| concern_family | 0.9922 | 0.9735 |
| risk_label | 0.7482 | 0.8073 |

These are not manually verified regulatory scores. They show the weak-label layer is learnable and consistent enough to use as a candidate-routing signal.

The local API now attaches `product_label_model` and `candidate_chemical_linkages` to product analysis results. These are candidate associations such as food processing byproducts, ceramic/glass heavy-metal signals, or vinyl/plasticizer signals; they are not confirmed product composition.

## Benchmark structure

The benchmark is split into layers.

### Stage 1: OCR and text extraction

- [run_gemma4_ocr_benchmark.py](/Users/adelie/Projects/gemma4good/run_gemma4_ocr_benchmark.py)
- [run_stage1_ocr_judge_benchmark.py](/Users/adelie/Projects/gemma4good/run_stage1_ocr_judge_benchmark.py)

Real-image OCR benchmark example:

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python build_real_ocr_cases.py
python run_gemma4_ocr_benchmark.py --cases benchmark_ocr_real_cases.json
python run_stage1_ocr_judge_benchmark.py --cases benchmark_ocr_real_cases.json
```

Current reference outputs:

- `/Users/adelie/Projects/gemma4good/outputs/ocr_benchmark/20260504_224129/ocr_report.md`
- `/Users/adelie/Projects/gemma4good/outputs/ocr_stage1_openai_judge/20260504_225827/stage1_report.md`

### Stage 2: shared post-input reasoning

This stage now uses the same `NormalizedProductPayload` contract as the app path.

This stage should be the same whether the user started from:

- uploaded images, then OCR/structuring
- direct text entry

Raw Stage 2:

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python build_category_reference.py
python run_stage2_text_benchmark.py
```

Grounded Stage 2 with Gemma:

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python run_stage2_grounded_benchmark.py --provider gemma
```

Grounded OpenAI reference comparison:

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python run_stage2_grounded_benchmark.py --provider openai
```

Current reference outputs:

- Raw Stage 2: `/Users/adelie/Projects/gemma4good/outputs/stage2_text_benchmark/20260504_233022/stage2_report.md`
- Grounded Gemma latest: `/Users/adelie/Projects/gemma4good/outputs/stage2_grounded_benchmark/gemma_20260505_102828/stage2_grounded_report.md`
- Grounded OpenAI reference: `/Users/adelie/Projects/gemma4good/outputs/stage2_grounded_benchmark/openai_20260505_085505/stage2_grounded_report.md`
- Iteration summary: `/Users/adelie/Projects/gemma4good/outputs/stage2_grounded_benchmark/stage2_iteration_summary_20260505.md`

### Distribution analysis and coverage scans

These help identify weak categories instead of only looking at mean score.

- [database/analyze_stage2_score_distribution.py](/Users/adelie/Projects/gemma4good/database/analyze_stage2_score_distribution.py)
- [database/run_stage2_coverage_scan.py](/Users/adelie/Projects/gemma4good/database/run_stage2_coverage_scan.py)

Current outputs:

- Raw distribution: `/Users/adelie/Projects/gemma4good/database/outputs/stage2_score_distribution/raw_report.md`
- Grounded distribution: `/Users/adelie/Projects/gemma4good/database/outputs/stage2_score_distribution/grounded_report.md`
- Coverage scan outputs: `/Users/adelie/Projects/gemma4good/database/outputs/stage2_coverage_scan/`

## One-command benchmark suite

A convenience runner is available at:

- [run_vnext_benchmark_suite.py](/Users/adelie/Projects/gemma4good/run_vnext_benchmark_suite.py)

Dry run:

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python run_vnext_benchmark_suite.py --dry-run
```

Run selected layers:

```bash
python run_vnext_benchmark_suite.py --stage1 --stage2-raw --stage2-grounded --coverage-scan
```

## Current benchmark reading

The current evidence suggests:

- Gemma 4 still needs better OCR/preprocessing for small, rotated, multilingual, or ingredient-panel images.
- The recent heavy agentic flow worsened overall benchmark performance because it made the intermediate payload too lossy and too verbose.
- The better direction is a thin agentic UX with a compact, benchmarkable core: OCR/text normalization, product-label classifier, local database retrieval, then Gemma final explanation.
- Product-risk mapping should be deterministic where the science/regulatory logic is rule-like: Gemma extracts product facts and process/material clues, while `product_risk_formatter.py` separates listed ingredients, process-derived compounds, packaging/contact-material pathways, category-based inferences, and nutrition-only context.
- Current pathway rules cover refined oils, high-temperature foods, smoked/cured meats, soft PVC/phthalates, non-stick/PFAS, composite wood/formaldehyde, dyed textiles/azo dyes, flame-retardant foam, and surfactant families without treating broad words like `vegetable oil`, `corn syrup`, or `surfactant` as automatically toxic.
- The system should continue to optimize around a fixed-size Gemma product path rather than shifting toward a larger model.
