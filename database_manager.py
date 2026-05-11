from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Optional


class ProductDatabase:
    """
    A persistent local storage for product information fetched from retail sites.
    Acts as a cache to speed up repeated queries and builds a dataset for fine-tuning.
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = Path(db_path) if db_path else Path(__file__).resolve().parent / "data/app_data/gemma4good.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product_cache (
                    url TEXT PRIMARY KEY,
                    product_name TEXT,
                    category TEXT,
                    ingredients TEXT,
                    materials TEXT,
                    warnings TEXT,
                    safety_concerns TEXT,
                    product_text TEXT,
                    last_fetched TIMESTAMP
                )
            """)
            conn.commit()

    def get_product(self, url: str) -> Optional[dict[str, Any]]:
        """Retrieve cached product data for a given URL."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM product_cache WHERE url = ?", (url,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def save_product(self, url: str, data: dict[str, Any]):
        """Save or update product data in the cache with validation."""
        name = data.get("product_name", "").lower()
        text = data.get("product_text", "").lower()
        
        # Validation: Block technical noise and known bot-block phrases
        junk_keywords = [
            "https",
            "protocol",
            "wikipedia",
            "continue shopping",
            "access denied",
            "robot",
            "general disclaimer",
            "content on this site is for reference purposes only",
        ]
        if any(k in name for k in junk_keywords) and not any(p in name for p in ["detergent", "cookie", "everspring"]):
             print(f"Validation failed for {url}: Result looks like technical noise. Not saving.")
             return

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO product_cache (
                    url, product_name, category, ingredients, 
                    materials, warnings, safety_concerns, 
                    product_text, last_fetched
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                url,
                data.get("product_name", ""),
                data.get("category", ""),
                data.get("ingredients", "") or data.get("ingredients_text", ""),
                data.get("materials", ""),
                data.get("warnings", "") or data.get("warning_text", ""),
                data.get("safety_concerns", "") or data.get("claims", ""),
                data.get("product_text", ""),
                datetime.now().isoformat()
            ))
            conn.commit()

    def list_all_products(self):
        """Returns all stored products (useful for dataset exports)."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM product_cache ORDER BY last_fetched DESC")
            return [dict(row) for row in cursor.fetchall()]


if __name__ == "__main__":
    # Quick test
    db = ProductDatabase()
    test_url = "https://example.com/product"
    db.save_product(test_url, {"product_name": "Test Cookie", "category": "Food"})
    print("Saved product:", db.get_product(test_url))
