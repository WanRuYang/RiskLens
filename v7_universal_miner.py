import csv
import json
import re
import random
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent
RAW_DATA_ROOT = PROJECT_ROOT / "data" / "data"
OUTPUT_DIR = PROJECT_ROOT / "data" / "finetuning"
OUTPUT_FILE = OUTPUT_DIR / "universal_forensic_dataset_v7.jsonl"

STORES = ["Walmart", "Target", "Sayweee", "Ranch 99", "Amazon", "Safeway", "99 Ranch Market", "H Mart"]

FOOD_KEYWORDS = ["Organic", "Premium", "Classic", "Sweet", "Salty", "Spicy", "Fresh", "Instant"]
FOOD_TYPES = ["Snack", "Beverage", "Drink", "Canned", "Powder", "Syrup", "Condiment", "Sauce", "Seasoning"]

OTHER_KEYWORDS = ["Heavy Duty", "Industrial", "Professional", "Safety", "Kids", "Household", "Medical Grade"]
OTHER_TYPES = ["Cleaner", "Adhesive", "Toy", "Cable", "Mug", "Ceramic", "Paint", "Lubricant", "Cosmetic", "Lotion"]

def normalize_key(text):
    if not text: return ""
    return re.sub(r'[^a-z0-9]', '', text.lower())

def load_all_databases():
    all_files = list(RAW_DATA_ROOT.glob("*.csv"))
    master_db = defaultdict(lambda: {"names": set(), "cas_numbers": set(), "records": []})
    
    print(f"Mining {len(all_files)} granular databases...")
    
    for csv_path in all_files:
        try:
            with csv_path.open(newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get("substance_name") or row.get("preferred_name") or row.get("name")
                    cas = row.get("cas_number") or row.get("cas")
                    
                    if not name and not cas:
                        continue
                        
                    # Use CAS as primary key if available, else normalized name
                    key = cas if cas and len(cas) > 5 else normalize_key(name)
                    if not key:
                        continue
                        
                    master_db[key]["records"].append({
                        "source": csv_path.name,
                        "data": row
                    })
                    if name: master_db[key]["names"].add(name)
                    if cas: master_db[key]["cas_numbers"].add(cas)
        except Exception as e:
            print(f"Error reading {csv_path.name}: {e}")
            
    return master_db

def synthesize_forensic_prompt(key, profile):
    # Determine if it looks more like food or other based on source files or random
    is_food = any("food" in r["source"].lower() or "gsfa" in r["source"].lower() or "jecfa" in r["source"].lower() for r in profile["records"])
    
    # We will force the 70/30 ratio at the loop level, but this helps pick better product names
    return is_food

def build_v7_dataset(target_size=5000):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    master_db = load_all_databases()
    
    keys = list(master_db.keys())
    random.shuffle(keys)
    
    dataset = []
    food_target = int(target_size * 0.7)
    other_target = target_size - food_target
    
    current_food = 0
    current_other = 0
    
    print(f"Synthesizing {target_size} universal forensic pairs...")
    
    # Loop until we hit target size
    idx = 0
    while len(dataset) < target_size:
        key = keys[idx % len(keys)]
        idx += 1
        profile = master_db[key]
        
        # Decide category based on targets
        # Try to match the actual nature of the chemical if possible
        inherent_is_food = any("food" in r["source"].lower() or "jecfa" in r["source"].lower() for r in profile["records"])
        
        if inherent_is_food and current_food < food_target:
            category = "food"
            current_food += 1
        elif not inherent_is_food and current_other < other_target:
            category = "other"
            current_other += 1
        elif current_food < food_target:
            category = "food"
            current_food += 1
        elif current_other < other_target:
            category = "other"
            current_other += 1
        else:
            break
            
        name = list(profile["names"])[0] if profile["names"] else "Unknown Substance"
        store = random.choice(STORES)
        
        # 1. Synthesize Forensic Label
        if category == "food":
            product_name = f"{random.choice(FOOD_KEYWORDS)} {name} {random.choice(FOOD_TYPES)}"
        else:
            product_name = f"{random.choice(OTHER_KEYWORDS)} {name} {random.choice(OTHER_TYPES)}"
            
        label_text = f"Label from {store}: {product_name}. Ingredients: {name}, preservatives, flavorings."
        
        # 2. Build Expert Context (Input)
        context = f"FORENSIC INPUT:\nSource: {store}\nLabel: {label_text}\n\nGRANULAR REGULATORY OVERLAP:\n"
        
        for i, rec in enumerate(profile["records"][:6]):
            d = rec["data"]
            source_name = rec["source"].replace(".csv", "")
            context += f"- Source [{source_name}]: "
            context += f"Status: {d.get('regulatory_status', 'N/A')}. "
            context += f"Hazard: {d.get('hazard_basis', 'N/A')}. "
            if d.get("threshold_value"):
                context += f"Limit: {d.get('threshold_value')} {d.get('threshold_unit', '')}. "
            if d.get("product_scope"):
                context += f"Scope: {d.get('product_scope')}. "
            context += "\n"
            
        # 3. Build Expert Verdict (Output)
        verdict = f"Expert Forensic Analysis for {product_name}:\n"
        verdict += f"The substance '{name}' (CAS: {next(iter(profile['cas_numbers']), 'N/A')}) is identified. "
        
        # Reason across sources
        has_prohibition = any("Prohibited" in str(r["data"].get("regulatory_status")) or "Banned" in str(r["data"].get("regulatory_status")) for r in profile["records"])
        has_authorized = any("Authorised" in str(r["data"].get("regulatory_status")) or "authorized" in str(r["data"].get("regulatory_status")).lower() for r in profile["records"])
        
        if has_prohibition:
            verdict += "CRITICAL: This substance is listed as PROHIBITED in at least one global jurisdiction. "
        elif has_authorized:
            verdict += "NOTE: This substance is AUTHORIZED with conditions in some jurisdictions, but requires careful threshold monitoring. "
            
        # Regional logic
        if any("prop65" in r["source"].lower() for r in profile["records"]):
            verdict += "California's Proposition 65 requires clear warning labels for this substance. "
        if any("eu_" in r["source"].lower() or "echa" in r["source"].lower() for r in profile["records"]):
            verdict += "European Union regulations maintain strict safety thresholds for this substance. "
            
        verdict += "\n\nVERDICT: "
        if has_prohibition:
            verdict += "HIGH RISK / AVOID. Prohibited status in global databases suggests significant safety concerns."
        else:
            verdict += "MONITORED USE. Substance is regulated with safe-harbor or usage conditions. Review concentration vs regional limits."

        dataset.append({
            "instruction": "Perform a multi-jurisdictional forensic safety audit based on granular regulatory data and literal label transcription.",
            "input": context.strip(),
            "output": verdict.strip()
        })

    print(f"Writing {len(dataset)} samples to {OUTPUT_FILE}...")
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for entry in dataset:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    build_v7_dataset(target_size=5500) # Aim slightly higher
