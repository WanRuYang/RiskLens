# gemma4good

A local, evidence-grounded consumer safety assistant built around a fixed-size Gemma 4 model.

Hazardly uses Gemma 4 as the multimodal model backend. Gemma 4 is subject to its own license and acceptable use terms. This project does not provide medical, legal, or regulatory advice; it provides evidence-grounded product risk summaries for informational purposes only.

## Project stance

`Gemma 4` is the intended product model.

`OpenAI` is used only for:

- benchmark judging
- reference comparisons
- methodology validation

It is **not** the intended production model for the mobile app.

## Current recommended architecture

The recommended direction is:

- agentic user experience
- linear, benchmarkable core pipeline
- grounded retrieval through the local API
- compact product-label classifier for category/pathway/concern routing
- explicit category and material reasoning
- review-queue capture for hard OCR and category cases

This means:

1. accept one chat-style multimodal turn at a time, then auto-detect whether the user provided images, a URL, or typed product text
2. if that mode is insufficient, recommend a better method instead of forcing a weak answer
3. extract or normalize text into one shared payload
4. confirm OCR or category only when needed
4. call the local API for grounded retrieval
5. generate the final answer with Gemma 4
6. store hard cases for future review and improvement

Supporting design docs:

- [/Users/adelie/Projects/gemma4good/docs/design_vnext.md](/Users/adelie/Projects/gemma4good/docs/design_vnext.md)
- [/Users/adelie/Projects/gemma4good/docs/test_plan_vnext.md](/Users/adelie/Projects/gemma4good/docs/test_plan_vnext.md)
- [/Users/adelie/Projects/gemma4good/docs/platform_targets.md](/Users/adelie/Projects/gemma4good/docs/platform_targets.md)
- [/Users/adelie/Projects/gemma4good/docs/pixel8_client_plan.md](/Users/adelie/Projects/gemma4good/docs/pixel8_client_plan.md)
- [/Users/adelie/Projects/gemma4good/docs/android_contract_mapping.md](/Users/adelie/Projects/gemma4good/docs/android_contract_mapping.md)
- [/Users/adelie/Projects/gemma4good/docs/run_on_pixel8.md](/Users/adelie/Projects/gemma4good/docs/run_on_pixel8.md)
- [/Users/adelie/Projects/gemma4good/docs/demo_plan.md](/Users/adelie/Projects/gemma4good/docs/demo_plan.md)

## Repo structure

```text
gemma4good/
├── app.py
├── app_openai.py
├── app_shared.py
├── platform_profiles.py
├── vnext_contract.py
├── prompt_utils.py
├── product_label_classifier.py
├── android_contract/
│   ├── Gemma4GoodApiModels.kt
│   ├── Gemma4GoodApiService.kt
│   ├── Gemma4GoodContractAdapters.kt
│   ├── RetrofitUsageExample.md
│   └── README.md
├── android_client/
│   ├── settings.gradle.kts
│   ├── build.gradle.kts
│   ├── README.md
│   └── app/
├── prompts/
│   ├── system_prompt.md
│   └── category_reference.json
├── benchmark_cases.json
├── benchmark_amazon_100.csv
├── benchmark_ocr_cases.json
├── benchmark_ocr_real_cases.json
├── benchmark_images/
├── benchmark_images_real/
├── run_gemma4_ocr_benchmark.py
├── run_stage1_ocr_judge_benchmark.py
├── run_stage2_text_benchmark.py
├── run_stage2_grounded_benchmark.py
├── run_vnext_benchmark_suite.py
├── scripts/
│   ├── build_prop65_label_dataset.py
│   └── train_product_label_classifier.py
├── models/
│   └── product_label_classifier/
├── test_app_flow.py
├── test_app_flow_openai.py
├── outputs/
├── docs/
└── data/
```

## Production path vs evaluation path

### Production-oriented path

- [app.py](/Users/adelie/Projects/gemma4good/app.py)
- [app_shared.py](/Users/adelie/Projects/gemma4good/app_shared.py)
- [vnext_contract.py](/Users/adelie/Projects/gemma4good/vnext_contract.py)
- [product_label_classifier.py](/Users/adelie/Projects/gemma4good/product_label_classifier.py)
- local FastAPI + Postgres retrieval layer
- category and material reasoning
- user history and hard-case review queue

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

## Current app intake flow

The current mac app now uses a single chat-style multimodal composer. The user can:

- type product text or a product description
- paste a product URL
- attach up to 3 images such as the product front, ingredients panel, a Prop 65 warning sticker, or phone-camera photos

Behind the scenes, the app auto-detects whether the turn is primarily image-based, URL-based, or text-based. It then normalizes that turn into one grounded payload before retrieval. If the input is too weak, the app should ask for clearer images, a corrected URL, or more text instead of forcing the user to manage modes manually.

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

- [/Users/adelie/Documents/New project/database/analyze_stage2_score_distribution.py](/Users/adelie/Documents/New%20project/database/analyze_stage2_score_distribution.py)
- [/Users/adelie/Documents/New project/database/run_stage2_coverage_scan.py](/Users/adelie/Documents/New%20project/database/run_stage2_coverage_scan.py)

Current outputs:

- Raw distribution: `/Users/adelie/Documents/New project/database/outputs/stage2_score_distribution/raw_report.md`
- Grounded distribution: `/Users/adelie/Documents/New project/database/outputs/stage2_score_distribution/grounded_report.md`
- Latest 100-case coverage scan: `/Users/adelie/Documents/New project/database/outputs/stage2_coverage_scan/20260505_104800/coverage_report.md`

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
