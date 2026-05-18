import sqlite3
import tempfile
from pathlib import Path

from database_manager import ProductDatabase


def test_existing_product_cache_gets_logic_version_column() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "cache.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE product_cache (
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
                """
            )

        db = ProductDatabase(str(db_path))
        with db._get_connection() as conn:
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(product_cache)").fetchall()
            }
        assert "logic_version" in columns
        assert "ingredient_panel_found" in columns
        assert "ingredient_panel_text" in columns

        db.save_product(
            "https://example.com/product",
            {
                "product_name": "Example Product",
                "ingredient_panel_found": True,
                "ingredient_panel_text": "partial ingredient panel",
            },
            logic_version="26.11",
        )
        row = db.get_product("https://example.com/product")
        assert row is not None
        assert row["logic_version"] == "26.11"
        assert row["ingredient_panel_found"] == 1
        assert row["ingredient_panel_text"] == "partial ingredient panel"


if __name__ == "__main__":
    test_existing_product_cache_gets_logic_version_column()
    print("Product cache migration checks: PASS")
