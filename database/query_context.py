from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the local gemma4good PostgreSQL database and return grounded context."
    )
    parser.add_argument("--product-text", default="", help="Product name or OCR product text.")
    parser.add_argument("--ingredients-text", default="", help="Ingredient list or material clues.")
    parser.add_argument("--warning-text", default="", help="Warning label text, if present.")
    parser.add_argument("--region", default="", help="Region or jurisdiction label.")
    parser.add_argument(
        "--dsn",
        default="",
        help="Optional PostgreSQL DSN. Defaults to GEMMA4GOOD_PG_DSN or dbname=gemma4good.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    conn = service.get_connection(args.dsn or "dbname=gemma4good")
    try:
        payload = service.build_grounding_context(
            conn,
            product_text=args.product_text or None,
            ingredients_text=args.ingredients_text or None,
            warning_text=args.warning_text or None,
            region_label=args.region or None,
        )
    finally:
        conn.close()

    if args.pretty:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
