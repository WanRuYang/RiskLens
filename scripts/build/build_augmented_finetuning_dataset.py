import csv
import json
import re
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent
RAW_DATA_ROOT = PROJECT_ROOT / "data" / "data"
AMAZON_100 = PROJECT_ROOT / "benchmark_amazon_100.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "finetuning"
OUTPUT_FILE = OUTPUT_DIR / "global_grocery_augmentation_v1.jsonl"

def normalize_name(name):
    if not name: return ""
    return re.sub(r'[^a-z0-9]', '', name.lower())

def load_csv(path):
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def build_augmented_dataset():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Loading regulatory databases for cross-referencing...")
    prop65 = load_csv(RAW_DATA_ROOT / "prop65_full_clean.csv")
    eu_food = load_csv(RAW_DATA_ROOT / "eu_food_additives.csv")
    iarc = load_csv(RAW_DATA_ROOT / "who_iarc_cancer_risk_list.csv")
    
    # Simple Indexing
    p65_names = {normalize_name(row['substance_name']) for row in prop65}
    eu_db = {normalize_name(row['substance_name']): row for row in eu_food}
    iarc_db = {normalize_name(row['substance_name']): row for row in iarc}
    
    # Load Amazon Grocery Products
    amazon_products = load_csv(AMAZON_100)
    
    dataset = []
    print(f"Analyzing {len(amazon_products)} Amazon products for non-Prop65 signals...")
    
    for product in amazon_products:
        title = product.get("amazon_seed_title", "")
        # In a real scenario, we'd have a column for ingredients. 
        # Here we'll simulate by checking if the title contains known substances 
        # OR just use the title as the search key.
        
        norm_title = normalize_name(title)
        
        # 1. Check if product is in Prop 65 (Simulated check)
        is_p65 = any(name in norm_title for name in p65_names if len(name) > 4)
        
        # 2. Search for non-Prop65 signals (EU / IARC)
        found_signals = []
        
        # Check for EU Additives (e.g., Titanium Dioxide, Aspartame, etc.)
        for chem, row in eu_db.items():
            if len(chem) > 5 and chem in norm_title:
                found_signals.append({
                    "source": "EU Food Additive",
                    "chemical": row['substance_name'],
                    "status": row['regulatory_status'],
                    "conditions": row['threshold_conditions']
                })

        # Check for IARC (e.g., Aloe Vera, Aspartame, etc.)
        for chem, row in iarc_db.items():
            if len(chem) > 5 and chem in norm_title:
                found_signals.append({
                    "source": "WHO IARC",
                    "chemical": row['substance_name'],
                    "status": row['regulatory_status'],
                    "basis": row['hazard_basis']
                })

        if found_signals:
            # We found a product that has risks in EU/WHO but potentially not in P65
            # (Or even if in P65, we focus on the global context)
            
            context = f"Product: {title}\n"
            context += f"Observed Regional Signal: {'None in Prop 65' if not is_p65 else 'Listed in Prop 65'}\n"
            context += "Global Evidence:\n"
            for sig in found_signals:
                context += f"- {sig['source']}: {sig['chemical']} is {sig['status']}. Details: {sig.get('conditions') or sig.get('basis')}\n"
                
            # Build Reasoning: Global Auditor Persona
            verdict = f"Global Safety Audit for '{title}':\n"
            if not is_p65:
                verdict += "While this product does not carry a California Prop 65 warning, global evidence suggests caution. "
            else:
                verdict += "This product is noted by Prop 65, and international data provides additional context. "
            
            verdict += "Specifically, " + "; ".join([f"{s['source']} notes {s['chemical']} as {s['status']}" for s in found_signals]) + ".\n"
            verdict += "Recommendation: Occasional use is likely low concern, but users sensitive to EU-authorized additives should review the detailed ingredient list."

            dataset.append({
                "instruction": "Evaluate the product safety using a global multi-jurisdiction perspective.",
                "input": context.strip(),
                "output": verdict.strip()
            })

    print(f"Writing {len(dataset)} augmented pairs to {OUTPUT_FILE}...")
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for entry in dataset:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    build_augmented_dataset()
