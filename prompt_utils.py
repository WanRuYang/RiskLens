from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = PROJECT_ROOT / "prompts" / "system_prompt.md"
CATEGORY_REFERENCE_PATH = PROJECT_ROOT / "prompts" / "category_reference.json"

_SYSTEM_PROMPT_CACHE: str | None = None
_CATEGORY_REFERENCE_CACHE: dict[str, Any] | None = None


def load_system_prompt() -> str:
    global _SYSTEM_PROMPT_CACHE
    if _SYSTEM_PROMPT_CACHE is None:
        _SYSTEM_PROMPT_CACHE = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    return _SYSTEM_PROMPT_CACHE


def load_category_reference() -> dict[str, Any]:
    global _CATEGORY_REFERENCE_CACHE
    if _CATEGORY_REFERENCE_CACHE is None:
        _CATEGORY_REFERENCE_CACHE = json.loads(CATEGORY_REFERENCE_PATH.read_text(encoding="utf-8"))
    return _CATEGORY_REFERENCE_CACHE


def category_reference_summary() -> str:
    entries = load_category_reference().get("entries", [])
    lines = []
    for entry in entries:
        keywords = ", ".join(entry.get("keywords", [])[:8])
        lines.append(
            f"- {entry['reference_id']}: use={entry['product_use_category']}; "
            f"material_or_form={entry['material_or_form']}; "
            f"priority={entry['information_priority']}; "
            f"keywords={keywords}"
        )
    return "\n".join(lines)


def format_prompt(
    *,
    task_name: str,
    instructions: str,
    payload: str | None = None,
    include_category_reference: bool = False,
) -> str:
    parts = [
        load_system_prompt(),
        f"## Current Task\n{task_name}",
    ]
    if include_category_reference:
        parts.append(
            "## Category Reference\nUse this small reference set when categorizing the product. "
            "Choose the best match when possible rather than inventing a new category.\n"
            + category_reference_summary()
        )
    parts.append(f"## Task Instructions\n{instructions.strip()}")
    if payload:
        parts.append(f"## Task Input\n{payload.strip()}")
    return "\n\n".join(parts).strip()


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {}
