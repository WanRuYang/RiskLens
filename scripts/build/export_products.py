import json
import csv
from pathlib import Path
from database_manager import ProductDatabase

def export_db():
    db = ProductDatabase()
    products = db.list_all_products()
    
    if not products:
        print("Database is empty.")
        return

    # Export to JSON
    json_path = Path("data/app_data/product_export.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    
    # Export to CSV
    csv_path = Path("data/app_data/product_export.csv")
    if products:
        keys = products[0].keys()
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(products)

    print(f"Exported {len(products)} products to:")
    print(f"- {json_path}")
    print(f"- {csv_path}")

if __name__ == "__main__":
    export_db()
