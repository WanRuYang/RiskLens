import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import kagglehub
import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor


VARIATION = "gemma-4-e4b-it"
MODEL_HANDLE = f"google/gemma-4/transformers/{VARIATION}"
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CASES_PATH = PROJECT_ROOT / "benchmark_ocr_cases.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "ocr_benchmark"


def load_kaggle_credentials() -> bool:
    kaggle_dir = Path.home() / ".kaggle"
    user_file = kaggle_dir / "user_name"
    token_file = kaggle_dir / "access_token"
    if not user_file.exists() or not token_file.exists():
        return False
    os.environ["KAGGLE_USERNAME"] = user_file.read_text().strip()
    os.environ["KAGGLE_KEY"] = token_file.read_text().strip()
    return True


def load_model() -> tuple[AutoProcessor, AutoModelForCausalLM]:
    if not load_kaggle_credentials():
        raise RuntimeError("Kaggle credentials not found under ~/.kaggle.")
    model_path = kagglehub.model_download(MODEL_HANDLE)
    processor = AutoProcessor.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    return processor, model


def load_cases(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text())


def build_prompt() -> str:
    return (
        "Extract visible text from this product image as faithfully as possible. "
        "Focus on product name, ingredients, warning text, and regulatory text. "
        "Return plain text only. Do not summarize. Preserve line breaks when useful."
    )


def run_ocr(processor: AutoProcessor, model: AutoModelForCausalLM, image_path: Path) -> str:
    image = Image.open(image_path).convert("RGB")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": build_prompt()},
            ],
        }
    ]
    prompt_str = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    inputs = processor(text=prompt_str, images=image, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=300, do_sample=False)
    response = processor.decode(output[0][inputs.input_ids.shape[-1] :], skip_special_tokens=True)
    return response.strip()


def run_ocr_multi(
    processor: AutoProcessor,
    model: AutoModelForCausalLM,
    image_paths: list[Path],
) -> str:
    chunks: list[str] = []
    for idx, image_path in enumerate(image_paths, start=1):
        extracted = run_ocr(processor, model, image_path)
        chunks.append(f"### Image {idx}\n{extracted}")
    return "\n\n".join(chunks).strip()


def score_case(extracted_text: str, expected_strings: list[str]) -> dict[str, Any]:
    extracted_lower = extracted_text.lower()
    results = []
    hit_count = 0
    for item in expected_strings:
        hit = item.lower() in extracted_lower
        results.append({"expected": item, "hit": hit})
        hit_count += int(hit)
    recall = hit_count / len(expected_strings) if expected_strings else 1.0
    return {
        "expected_count": len(expected_strings),
        "hit_count": hit_count,
        "substring_recall": round(recall, 4),
        "matches": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Gemma 4 text extraction from product images.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if args.limit > 0:
        cases = cases[: args.limit]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = DEFAULT_OUTPUT_ROOT / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    if not cases:
        (output_dir / "README.txt").write_text(
            "No OCR benchmark cases were provided. Add cases to benchmark_ocr_cases.json and rerun.\n"
        )
        print(f"Output directory: {output_dir}")
        print("No OCR benchmark cases found.")
        return

    processor, model = load_model()

    outputs: dict[str, Any] = {}
    summary_rows: list[dict[str, Any]] = []
    for idx, case in enumerate(cases, start=1):
        case_id = case["id"]
        image_paths_raw = case.get("image_paths")
        if image_paths_raw:
            image_paths = [Path(path) for path in image_paths_raw]
        else:
            image_paths = [Path(case["image_path"])]
        expected_strings = case.get("expected_strings", [])
        print(f"[{idx}/{len(cases)}] Running OCR case: {case_id}")
        extracted_text = run_ocr_multi(processor, model, image_paths)
        score = score_case(extracted_text, expected_strings)
        outputs[case_id] = {
            "image_paths": [str(path) for path in image_paths],
            "expected_strings": expected_strings,
            "extracted_text": extracted_text,
            "score": score,
        }
        summary_rows.append(
            {
                "case_id": case_id,
                "image_paths": [str(path) for path in image_paths],
                "substring_recall": score["substring_recall"],
                "expected_count": score["expected_count"],
                "hit_count": score["hit_count"],
            }
        )

    (output_dir / "ocr_outputs.json").write_text(json.dumps(outputs, indent=2, ensure_ascii=False))
    (output_dir / "ocr_summary.json").write_text(json.dumps(summary_rows, indent=2, ensure_ascii=False))

    mean_recall = sum(row["substring_recall"] for row in summary_rows) / len(summary_rows)
    report_lines = [
        "# Gemma 4 OCR Benchmark",
        "",
        f"- Cases: `{len(summary_rows)}`",
        f"- Mean substring recall: `{mean_recall:.3f}`",
        "",
        "## Per-case",
    ]
    for row in summary_rows:
        report_lines.append(
            f"- `{row['case_id']}`: recall `{row['substring_recall']:.3f}` "
            f"({row['hit_count']}/{row['expected_count']})"
        )
    (output_dir / "ocr_report.md").write_text("\n".join(report_lines))
    print(f"Output directory: {output_dir}")
    print(f"Mean substring recall: {mean_recall:.3f}")


if __name__ == "__main__":
    main()
