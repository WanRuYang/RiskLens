# vNext Test Plan

## Testing Philosophy

The system should be evaluated in layers.

1. Stage 1: image reading and OCR extraction
2. Stage 2: structured category and material reasoning
3. Grounded retrieval quality
4. Final answer quality
5. Coverage scan on larger unlabeled product sets

The goal is to separate OCR errors from reasoning errors and retrieval errors.

## Test Layers

### Stage 1 OCR

Use real marketplace images and synthetic images.

Metrics:

- OpenAI-judged OCR fidelity
- completeness
- hallucination rate
- expected-string recall

### Stage 2 Structured Reasoning

Use the gold 8-case benchmark as the regression set. The benchmark payload should be the same object shape used by the app path.

Metrics:

- category exact
- material exact
- information priority exact
- category identification score
- risk response score
- recommendation alignment score
- source awareness score
- grounding fidelity score for grounded runs

Track not only mean but score distribution by product-use category.

### Grounded Retrieval

The grounded path should be checked for:

- direct chemical match vs category-level-only signal
- region-aware source typing
- correct recommendation bucket policy
- correct user-overlap summaries

### Deterministic Risk Formatter

The formatter should be tested separately from Gemma4 and database retrieval because it encodes rule-like product chemistry and regulatory framing.

Regression cases:

- cookies with vegetable oil
- potato chips fried in vegetable oil
- infant formula with palm oil
- plastic food container
- PVC shower curtain
- non-stick frying pan
- grease-resistant microwave popcorn bag
- corn syrup candy
- smoked red meat
- children's toy made of soft plastic
- composite wood nursery shelf
- dyed textile costume

Expected checks:

- broad ingredients such as `vegetable oil`, `corn syrup`, and `surfactant` are not labeled toxic by default
- inferred risks are labeled as `likely process-derived`, `packaging/contact material`, or `category-based risk`
- every risk candidate has source labels and dose/context language
- sensitive-group guidance is only elevated when the pathway supports it

Run:

```bash
/Users/adelie/Projects/gemma4good/.venv/bin/python -B /Users/adelie/Projects/gemma4good/test_risk_inference_rules.py
```

### 100-case Coverage Scan

Use the 100-case title benchmark as a broader coverage-health scan.

Track:

- known category rate
- known material rate
- direct chemical match rate
- category-level-only rate
- majority inferred category per benchmark group
- groups with highest unknown rates

This scan is not a replacement for the gold benchmark. It is a system-health signal.

## Current Best Reference Runs

### Stage 1

- OCR benchmark report: `/Users/adelie/Projects/gemma4good/outputs/ocr_benchmark/20260504_224129/ocr_report.md`
- OpenAI-judged Stage 1: `/Users/adelie/Projects/gemma4good/outputs/ocr_stage1_openai_judge/20260504_225827/stage1_report.md`

### Stage 2

- Raw Stage 2: `/Users/adelie/Projects/gemma4good/outputs/stage2_text_benchmark/20260504_233022/stage2_report.md`
- Grounded Gemma latest: `/Users/adelie/Projects/gemma4good/outputs/stage2_grounded_benchmark/gemma_20260505_102828/stage2_grounded_report.md`
- Grounded OpenAI reference: `/Users/adelie/Projects/gemma4good/outputs/stage2_grounded_benchmark/openai_20260505_085505/stage2_grounded_report.md`

### Distribution Analysis

- Raw distribution: `/Users/adelie/Documents/New project/database/outputs/stage2_score_distribution/raw_report.md`
- Grounded distribution: `/Users/adelie/Documents/New project/database/outputs/stage2_score_distribution/grounded_report.md`

### Coverage Scan

- Latest 100-case scan: `/Users/adelie/Documents/New project/database/outputs/stage2_coverage_scan/20260505_104800/coverage_report.md`

## Immediate Next Test Goals

1. keep the 8-case benchmark stable while changing the app design
2. improve the remaining ceramic lead source-framing miss
3. reduce unknowns in sports-and-hydration titles
4. reduce unknown materials in clothing-and-wearables and kitchen-home
5. start collecting real hard cases into the review queue


## Platform readiness checks

In addition to model-quality benchmarks, each iteration should preserve these portability checks:

1. the same Stage 2 payload can be produced from image or direct text input
2. the retrieval payload stays compact and typed
3. no desktop-only path assumptions leak into the product contract
4. the agentic flow can be implemented as a thin UI layer on both macOS and Android
5. OpenAI remains evaluation-only and is not required for the production path
