import random
import json
import csv
from pathlib import Path
from collections import defaultdict
from safety_lookup import SafetyKnowledgeBase

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = PROJECT_ROOT / "data" / "data"
OUTPUT_DIR = PROJECT_ROOT / "data" / "finetuning"
OUTPUT_FILE = OUTPUT_DIR / "massive_forensic_dataset_v6.jsonl"

STORES = ["Walmart", "Target", "Sayweee", "Ranch 99", "Amazon", "Safeway", "99 Ranch Market", "H Mart"]

FOOD_KEYWORDS = ["Organic", "Premium", "Classic", "Sweet", "Salty", "Spicy", "Fresh", "Instant"]
FOOD_TYPES = ["Snack", "Beverage", "Drink", "Canned", "Powder", "Syrup", "Condiment"]

OTHER_KEYWORDS = ["Heavy Duty", "Industrial", "Professional", "Safety", "Kids", "Household"]
OTHER_TYPES = ["Cleaner", "Adhesive", "Toy", "Cable", "Mug", "Ceramic", "Paint"]

def synthesize_product(name, category, store):
    """
    Synthesizes a realistic product label based on a chemical seed and store context.
    """
    if category == "food":
        keyword = random.choice(FOOD_KEYWORDS)
        ptype = random.choice(FOOD_TYPES)
    else:
        keyword = random.choice(OTHER_KEYWORDS)
        ptype = random.choice(OTHER_TYPES)
        
    return f"Product found at {store}: {keyword} {name} {ptype}. Contains: {name} and other additives."

def build_massive_dataset(target_size=1200):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Initializing SafetyKnowledgeBase for large-scale synthesis...")
    kb = SafetyKnowledgeBase()
    
    # Get all chemicals with any regulatory evidence
    evidence_rows = kb.evidence_rows
    chem_pool = []
    seen_ids = set()
    
    for row in evidence_rows:
        cid = row['chemical_id']
        if cid not in seen_ids:
            chem_pool.append({"id": cid, "name": row['preferred_name']})
            seen_ids.add(cid)
            
    random.shuffle(chem_pool)
    
    dataset = []
    food_count = int(target_size * 0.7)
    other_count = target_size - food_count
    
    print(f"Targeting {target_size} samples (Food: {food_count}, Other: {other_count})")
    
    for i in range(target_size):
        # Determine category based on remaining quota
        if food_count > 0:
            category = "food"
            food_count -= 1
        else:
            category = "other"
            other_count -= 1
            
        # Select a chemical (cycled if pool is smaller than target)
        chem = chem_pool[i % len(chem_pool)]
        store = random.choice(STORES)
        
        # 1. Synthesize Label
        label_text = synthesize_product(chem['name'], category, store)
        
        # 2. Expert Retrieval for Labeling
        # We simulate a confirmed text for retrieval
        retrieval = kb.retrieve("", label_text, "California, USA")
        
        reg_ev = retrieval.get("regulatory_evidence", [])
        sources = set()
        for row in reg_ev:
            sources.add(row.get("country_or_jurisdiction") or "International")
            
        # 3. Build Training Context (Input)
        context = f"Forensic Scan: {label_text}\n"
        context += f"Source: {store}\n"
        context += "Verified Regulatory Findings:\n"
        
        high_risk = False
        for row in reg_ev[:4]:
            context += f"- {row.get('country_or_jurisdiction')}: {row.get('regulatory_status')} | Hazard: {row.get('hazard_basis')} | Threshold: {row.get('threshold_value', 'n/a')} {row.get('threshold_unit', '')}\n"
            if "Listed" in str(row.get("regulatory_status")):
                high_risk = True

        # 4. Build Expert Verdict (Output)
        verdict = f"Forensic Safety Audit for {store} product:\n"
        verdict += f"The ingredient '{chem['name']}' triggers safety signals across {len(sources)} jurisdictions. "
        
        if "California" in str(sources):
            verdict += "A Prop 65 warning is likely required based on the CA listing. "
        if "European Union" in str(sources):
            verdict += "The EU maintains specific authorization limits for this substance. "
            
        verdict += f"\nRecommendation: "
        if high_risk:
            verdict += "HIGH CONCERN. Limit repeated exposure and cross-reference with safe-harbor levels."
        else:
            verdict += "LOWER CONCERN. Evidence suggests authorizated use, but regional conditions apply."

        dataset.append({
            "instruction": "Evaluate the safety of this marketplace product based on the literal label transcription and granular global rules.",
            "input": context.strip(),
            "output": verdict.strip(),
            "metadata": {
                "chemical": chem['name'],
                "store": store,
                "category": category
            }
        })

    print(f"Writing {len(dataset)} samples to {OUTPUT_FILE}...")
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for entry in dataset:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    build_massive_dataset(target_size=1200)
