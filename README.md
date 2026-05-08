# gemma4good

A local, evidence-grounded consumer safety assistant built around a fixed-size Gemma 4 model.

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
- explicit category and material reasoning
- review-queue capture for hard OCR and category cases

This means:

1. accept exactly one input mode at a time: image, URL, or text
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
- local FastAPI + Postgres retrieval layer
- category and material reasoning
- user history and hard-case review queue

### Evaluation-only path

- [app_openai.py](/Users/adelie/Projects/gemma4good/app_openai.py)
- [run_openai_pretest.py](/Users/adelie/Projects/gemma4good/run_openai_pretest.py)
- OpenAI-judged OCR benchmark
- OpenAI reference comparisons in Stage 2

Use this path only to evaluate Gemma 4 and the system design. Do not treat it as the intended deployment path.

## Local API dependency

The app expects the local FastAPI server from the database project to be running on:

- `http://127.0.0.1:8010`

Start it from the database project:

```bash
cd "/Users/adelie/Documents/New project/database"
python3 -m uvicorn api:app --host 127.0.0.1 --port 8010
```

## Run the app

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

## Current app input modes

The current app design supports three explicit input modes:

- image mode: 1 to 3 uploaded images plus optional product description
- URL mode: product page link
- text mode: typed product name / description

The shared contract normalizes these into one grounded payload before retrieval.

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

- Gemma 4 benefits strongly from system design improvements
- the largest gains so far came from grounded retrieval, category references, and recommendation-policy tuning
- remaining weak areas are category- or source-specific, not broad model-size limitations
- the current design should continue to optimize around a fixed-size Gemma product path rather than shifting toward a larger model
