import json
import random
from pathlib import Path
from safety_lookup import SafetyKnowledgeBase

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "finetuning"
OUTPUT_FILE = OUTPUT_DIR / "synthetic_hard_cases_v4.jsonl"

def generate_hard_cases():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Initializing SafetyKnowledgeBase for scenario synthesis...")
    kb = SafetyKnowledgeBase()
    
    # Identify chemicals with interesting profiles
    # We'll look for chemicals that appear in regulatory_evidence
    evidence = kb.evidence_rows
    chem_profiles = {}
    
    for row in evidence:
        cid = row['chemical_id']
        if cid not in chem_profiles:
            chem_profiles[cid] = {"name": row['preferred_name'], "sources": []}
        chem_profiles[cid]["sources"].append(row)

    # Filter for "Hard Cases" (at least 2 different jurisdictions or status types)
    hard_chemicals = []
    for cid, profile in chem_profiles.items():
        jurisdictions = {r['country_or_jurisdiction'] for r in profile['sources']}
        if len(jurisdictions) >= 1: # We'll take any with good data, prefer multi
            hard_chemicals.append(profile)

    dataset = []
    print(f"Synthesizing scenarios for {len(hard_chemicals)} high-value chemicals...")
    
    # Limit to ~200 to keep it focused
    sampled_chems = random.sample(hard_chemicals, min(200, len(hard_chemicals)))

    for chem in sampled_chems:
        name = chem["name"]
        sources = chem["sources"]
        
        # Create a synthetic label
        product_types = ["Premium Cleaner", "Daily Supplement", "Industrial Adhesive", "Kids Bath Soap", "Ceramic Glaze"]
        ptype = random.choice(product_types)
        
        label_text = f"Product: {ptype} Plus. Ingredients: Purified Water, {name}, Fragrance, Preservatives."
        
        # Build Context
        context = f"Forensic Label Scan: {label_text}\n"
        context += "Verified Regulatory Context:\n"
        for s in sources[:3]:
            context += f"- {s['country_or_jurisdiction']}: Status: {s['regulatory_status']} | Hazard: {s['hazard_basis']}\n"
            
        # Build Reasoning
        verdict = f"Forensic Safety Analysis for '{ptype} Plus':\n"
        verdict += f"The ingredient '{name}' is the primary substance of concern. "
        
        jur_list = [s['country_or_jurisdiction'] for s in sources]
        if "California" in str(jur_list):
            verdict += "California's Proposition 65 requires clear and reasonable warnings for this substance. "
        if "European Union" in str(jur_list):
            verdict += "The European Union maintains specific authorization conditions for this chemical. "
            
        verdict += f"\nSafety Verdict: This product requires a multi-region safety audit due to the presence of {name}. "
        verdict += "Occasional exposure might be acceptable under specific regional safe-harbor levels, but long-term repeated use should be evaluated."

        dataset.append({
            "instruction": "As a forensic safety expert, evaluate this synthetic product label using the provided regulatory data.",
            "input": context.strip(),
            "output": verdict.strip()
        })

    print(f"Writing {len(dataset)} synthetic hard cases to {OUTPUT_FILE}...")
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for entry in dataset:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    generate_hard_cases()
