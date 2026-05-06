# OCR Benchmark Notes

The app begins with one to three uploaded images, so OCR-like text extraction quality should be measured separately from regulation reasoning quality.

The benchmark should be treated as a two-stage pipeline:

1. image reading and text extraction
2. category identification plus grounded app reasoning

This file is about Stage 1 only.

## Purpose

This benchmark isolates:

- product name extraction
- ingredient extraction
- warning-text extraction
- regulatory text extraction from labels

It should not be mixed with the reasoning benchmark, because a model can fail for two very different reasons:

1. it did not read the image text correctly
2. it read the text correctly but mapped the regulation or concern incorrectly

## Files

- `benchmark_ocr_cases.json`
- `benchmark_ocr_real_cases.json`
- `run_gemma4_ocr_benchmark.py`
- `build_real_ocr_cases.py`
- `run_stage1_ocr_judge_benchmark.py`

## Case format

Each OCR case should look like:

```json
{
  "id": "sample_case",
  "image_paths": [
    "/absolute/path/to/front.jpg",
    "/absolute/path/to/ingredients.jpg",
    "/absolute/path/to/warning.jpg"
  ],
  "expected_strings": [
    "Titanium dioxide",
    "WARNING: Cancer and Reproductive Harm",
    "Ingredients"
  ]
}
```

## Run

```bash
python run_gemma4_ocr_benchmark.py
python build_real_ocr_cases.py
python run_gemma4_ocr_benchmark.py --cases benchmark_ocr_real_cases.json
python run_stage1_ocr_judge_benchmark.py --cases benchmark_ocr_real_cases.json
```

Or limit the number of cases:

```bash
python run_gemma4_ocr_benchmark.py --limit 5
```

## Current status

- `benchmark_ocr_cases.json` contains the larger synthetic benchmark set used to test the full OCR path.
- `benchmark_ocr_real_cases.json` is generated from `benchmark_real_image_manifest.csv` and currently points to a small batch of real marketplace front images.
- The real-image batch is useful for checking title extraction on actual marketplace imagery, but it is still incomplete because most cases do not yet include ingredient and warning panels.
- A current real-image OCR run is available at `outputs/ocr_benchmark/20260504_224129/ocr_report.md` with mean substring recall `0.764` across 6 real front-image cases.
- `run_stage1_ocr_judge_benchmark.py` adds a second Stage 1 view where OpenAI vision judges Gemma's OCR quality directly from the images.
