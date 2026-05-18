import argparse
import os
from pathlib import Path

import kagglehub
import torch
from transformers import AutoModelForCausalLM, AutoProcessor

from safety_lookup import SafetyKnowledgeBase


VARIATION = "gemma-4-e4b-it"
MODEL_HANDLE = f"google/gemma-4/transformers/{VARIATION}"


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


def build_prompt(grounding_context: str) -> str:
    return f"""
You are a cautious consumer product and ingredient guide.

Use ONLY the grounded context below.
Do not invent legal status, thresholds, or scientific findings that are not in the provided context.
If the context shows disagreement across jurisdictions or between regulators and literature, say so clearly.
Do not say a product is definitely safe or definitely unsafe unless the context directly supports that.

Your answer must have these sections:
## What We Found
## What The Sources Say
## What This Means For A Consumer
## Good Follow-Up Sources

In "What This Means For A Consumer":
- explain whether this looks more like higher concern, context-dependent concern, or likely lower concern
- explain whether occasional use may be okay, worth limiting, or worth avoiding
- if relevant, mention sugar or other non-chemical practical issues only if directly inferable from the product type

Grounded context:
{grounding_context}
""".strip()


def run_query(
    processor: AutoProcessor,
    model: AutoModelForCausalLM,
    prompt: str,
) -> str:
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    prompt_str = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    inputs = processor(text=prompt_str, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=500,
            do_sample=False,
        )
    generated_ids = output[0][inputs.input_ids.shape[-1] :]
    return processor.decode(generated_ids, skip_special_tokens=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a grounded Gemma 4 consumer-safety query using local CSV retrieval.")
    parser.add_argument("--product-name", required=True)
    parser.add_argument("--ingredients", default="")
    parser.add_argument("--region", default="California, USA")
    parser.add_argument("--question", default="")
    args = parser.parse_args()

    kb = SafetyKnowledgeBase()
    result = kb.retrieve(
        product_name=args.product_name,
        ingredients_text=args.ingredients,
        region=args.region,
        user_question=args.question,
    )
    grounding_context = kb.build_grounding_context(result)

    print("Loading model...", flush=True)
    processor, model = load_model()
    prompt = build_prompt(grounding_context)
    answer = run_query(processor, model, prompt)

    print("\n=== Grounding Context ===\n")
    print(grounding_context)
    print("\n=== Gemma Answer ===\n")
    print(answer)


if __name__ == "__main__":
    main()
