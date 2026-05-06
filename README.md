# gemma4good

Local Gemma 4 consumer safety assistant with:

- OCR from 1 to 3 uploaded product images
- local grounded lookup through a PostgreSQL-backed API
- category and material inference
- regulatory and warning-source explanation
- benchmark runners for raw reasoning and OCR quality

## Repo Structure

```text
gemma4good/
├── app.py
├── app_v0.py
├── benchmark_cases.json
├── benchmark_amazon_100.csv
├── benchmark_product_image_manifest.csv
├── benchmark_real_image_manifest.csv
├── benchmark_ocr_cases.json
├── benchmark_ocr_real_cases.json
├── benchmark_images/
├── benchmark_images_real/
├── build_image_benchmark_assets.py
├── build_category_reference.py
├── build_real_ocr_cases.py
├── data/
│   ├── app_data/
│   └── p65_data/
├── docs/
│   ├── ocr_benchmark_notes.md
│   ├── demo_plan.md
│   ├── writeup_v0.md
│   ├── writeup_v0.tex
│   └── writeup_v0.pdf
├── outputs/
├── prompts/
│   ├── category_reference.json
│   └── system_prompt.md
├── prompt_utils.py
├── app_openai.py
├── run_gemma4_grounded_query.py
├── run_gemma4_ocr_benchmark.py
├── run_gemma4_pretest.py
├── run_openai_pretest.py
├── safety_lookup.py
├── scripts/
├── test_app_flow.py
└── test_app_flow_openai.py
```

## Key Folders

- `data/app_data`
  - app-serving tables exported as CSV
  - chemical master, regulatory evidence, literature evidence, category mappings
- `data/p65_data`
  - Prop 65 scraper outputs and pattern analysis outputs
- `benchmark_images`
  - synthetic benchmark image cases generated for OCR and app-flow testing
- `benchmark_images_real`
  - small batch of real marketplace front images
- `outputs`
  - benchmark and app-flow test outputs
- `docs`
  - write-up, methodology, and OCR benchmark notes
  - demo plan for showcasing both consumer value and engineering design
- `prompts`
  - shared system-prompt text used by the app
  - small category reference used for product categorization
  - keeps category/material reasoning rules consistent across OCR structuring and final answer generation

## Current App Flow

1. User uploads 1 to 3 images.
2. User can optionally provide a product page link.
3. Gemma 4 extracts text from the images.
4. The app structures OCR output into:
   - product name
   - ingredient text
   - warning text
   - handling / caution text
5. The app calls the local API for grounded lookup.
6. The API returns:
   - product category and material inference
   - matched chemicals
   - regulatory evidence by source and region
   - recommendation bucket
   - repeated-chemical overlap from the user history
7. Gemma 4 turns the grounded result into the final user-facing explanation.

If a product page link is provided, it is treated as supporting context for product-title or category clues, not as proof of the exact ingredient list.

Reasoning priority rule:

- if the product is food, drink, supplement, or a household cleaner/spray, ingredient text matters most
- otherwise, material or construction clues matter most

## Local API Dependency

The app expects the local FastAPI server from the database project to be running on:

- `http://127.0.0.1:8010`

## Run the App

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python app.py
```

Run the OpenAI-backed app variant:

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python app_openai.py
```

## Run the End-to-End App Test

This uses synthetic benchmark images and writes a final report plus debug payload.

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python test_app_flow.py
```

Outputs:

- `outputs/app_flow_test/final_report.md`
- `outputs/app_flow_test/debug_payload.json`

Run the OpenAI-backed end-to-end app test against the same local API:

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python test_app_flow_openai.py
```

Outputs:

- `outputs/app_flow_test_openai/final_report.md`
- `outputs/app_flow_test_openai/debug_payload.json`

## OCR Benchmark

The benchmark should be interpreted in two stages:

- Stage 1: image reading and text extraction
- Stage 2: shared post-input reasoning from a normalized payload

Stage 2 should be the same whether the user started from:

- uploaded images, then OCR / structuring
- direct text entry

Stage 1 can be judged separately with an OpenAI vision model reviewing Gemma's OCR output.

Synthetic benchmark:

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python run_gemma4_ocr_benchmark.py
```

Real marketplace front-image benchmark:

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python build_real_ocr_cases.py
python run_gemma4_ocr_benchmark.py --cases benchmark_ocr_real_cases.json
```

Current real-image OCR run:

- `outputs/ocr_benchmark/20260504_224129/ocr_report.md`
- mean substring recall on 6 real front-image cases: `0.764`

Stage 1 OpenAI-judged OCR benchmark:

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python run_stage1_ocr_judge_benchmark.py --cases benchmark_ocr_real_cases.json
```

## Stage 2 Benchmark

Stage 2 uses a normalized post-input payload shared by:

- image -> OCR/structuring -> Stage 2
- direct text entry -> Stage 2

The current benchmark now uses a small dataset-derived category reference:

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python build_category_reference.py
python run_stage2_text_benchmark.py
```

Current improved Stage 2 run:

- `outputs/stage2_text_benchmark/20260504_233022/stage2_report.md`
- category exact accuracy: `1.000`
- material/form exact accuracy: `0.500`
- ingredient/material priority accuracy: `1.000`
- OpenAI risk response score: `4.375 / 5`

Grounded Stage 2 benchmark with the same local API:

```bash
cd /Users/adelie/Projects/gemma4good
source .venv/bin/activate
python run_stage2_grounded_benchmark.py --provider gemma
```

Or compare with the OpenAI-backed front-end against the same local API:

```bash
python run_stage2_grounded_benchmark.py --provider openai
```

The grounded benchmark is intended to show improvement from retrieval and system design while keeping the local Gemma model size fixed.

Current grounded benchmark outputs:

- Gemma grounded run:
  - `outputs/stage2_grounded_benchmark/gemma_20260505_000330`
- Gemma grounded run after matching and recommendation-policy fixes:
  - `outputs/stage2_grounded_benchmark/gemma_20260505_100209`
- OpenAI grounded reference run:
  - `outputs/stage2_grounded_benchmark/openai_20260505_085505`
- Iteration summary comparing raw vs grounded:
  - `outputs/stage2_grounded_benchmark/stage2_iteration_summary_20260505.md`

## Raw Reasoning Benchmark

Gemma raw:

```bash
python run_gemma4_pretest.py --limit 8
```

OpenAI baseline:

```bash
python run_openai_pretest.py --limit 8
```

## Notes

- `benchmark_images` is synthetic and meant to test OCR flow and app wiring.
- `benchmark_images_real` currently contains a small set of real marketplace front images only.
- Ingredient and warning panel images are still needed for a stronger real-image OCR benchmark.
- `docs/demo_plan.md` lays out the best live-demo sequence and how to explain the engineering choices.
