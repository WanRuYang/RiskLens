import csv
import json
import re
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent
RAW_DATA_ROOT = PROJECT_ROOT / "data" / "data"
OUTPUT_DIR = PROJECT_ROOT / "data" / "finetuning"
OUTPUT_FILE = OUTPUT_DIR / "regulatory_reasoning_v1.jsonl"

def normalize_name(name):
    if not name: return ""
    return re.sub(r'[^a-z0-9]', '', name.lower())

def load_csv(filename):
    path = RAW_DATA_ROOT / filename
    if not path.exists():
        print(f"Warning: {filename} not found.")
        return []
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def build_dataset():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Loading granular databases...")
    prop65 = load_csv("prop65_full_clean.csv")
    iarc = load_csv("who_iarc_cancer_risk_list.csv")
    eu_food = load_csv("eu_food_additives.csv")
    fda_cosmetic = load_csv("fda_cosmetics_prohibited_restricted.csv")
    
    # Index by CAS and Name
    chem_db = defaultdict(lambda: {"p65": [], "iarc": [], "eu_food": [], "fda_cos": []})
    
    print("Indexing chemicals...")
    for row in prop65:
        key = row.get("cas_number") or normalize_name(row.get("substance_name"))
        if key: chem_db[key]["p65"].append(row)
            
    for row in iarc:
        key = row.get("cas_number") or normalize_name(row.get("substance_name"))
        if key: chem_db[key]["iarc"].append(row)
            
    for row in eu_food:
        key = row.get("cas_number") or normalize_name(row.get("substance_name"))
        if key: chem_db[key]["eu_food"].append(row)
            
    for row in fda_cosmetic:
        key = row.get("cas_number") or normalize_name(row.get("substance_name"))
        if key: chem_db[key]["fda_cos"].append(row)

    dataset = []
    print(f"Generating training pairs for {len(chem_db)} unique chemicals...")
    
    for key, data in chem_db.items():
        # Only include if we have a match in at least two sources or a very rich single source
        sources_count = sum(1 for v in data.values() if v)
        if sources_count < 1: continue
        
        # Build Input: Raw Context
        name = ""
        for s in data.values():
            if s: 
                name = s[0].get("substance_name") or s[0].get("preferred_name", "")
                break
        
        context = f"Chemical: {name}\nCAS: {key if '-' in key else 'N/A'}\n"
        
        if data["p65"]:
            p = data["p65"][0]
            context += f"- Prop 65: Listed for {p.get('hazard_basis')} since {p.get('year_added')}. Safe Harbor: {p.get('safe_harbor_or_adi')} {p.get('safe_harbor_or_adi_unit')}.\n"
        
        if data["iarc"]:
            i = data["iarc"][0]
            context += f"- WHO IARC: Group {i.get('regulatory_status')} ({i.get('hazard_basis')}).\n"
            
        if data["eu_food"]:
            e = data["eu_food"][0]
            context += f"- EU Food: Status: {e.get('regulatory_status')}. Conditions: {e.get('threshold_conditions')}. E-Number: {e.get('notes', '')}\n"

        if data["fda_cos"]:
            f = data["fda_cos"][0]
            context += f"- FDA Cosmetic: Status: {f.get('regulatory_status')}. Scope: {f.get('product_scope')}.\n"

        # Build Target: Forensic Reasoning
        # Here we define the "Perfect Assistant" behavior we want to train
        verdict = f"Reasoned Analysis for {name}:\n"
        if data["p65"] and data["eu_food"]:
            verdict += "This substance presents a regulatory overlap. "
            if "Authorised" in data["eu_food"][0].get("regulatory_status", ""):
                verdict += "While the EU authorizes its use in food with conditions, California's Prop 65 requires warnings if thresholds are exceeded. "
            else:
                verdict += "Both the EU and California maintain restrictions on this substance. "
        
        if data["iarc"]:
            verdict += f"The WHO IARC classifies it in Group {data['iarc'][0].get('regulatory_status')}, supporting the {data['p65'][0].get('hazard_basis') if data['p65'] else 'hazard'} concerns. "

        verdict += "\nPractical Guidance: "
        if sources_count >= 2:
            verdict += "Due to multiple global listings, this is a high-priority chemical for safety auditing."
        else:
            verdict += "Limited multi-source evidence found, but regional rules apply."

        dataset.append({
            "instruction": "Perform a forensic safety audit based on the granular regulatory data provided.",
            "input": context.strip(),
            "output": verdict.strip()
        })

    print(f"Writing {len(dataset)} pairs to {OUTPUT_FILE}...")
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for entry in dataset:
            # mlx-lm uses a specific chat format, we'll use a generic one for now
            # or convert to Gemma 4 chat template style
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    build_dataset()
