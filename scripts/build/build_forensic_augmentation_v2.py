import json
import re
import csv
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent
RAW_DATA_ROOT = PROJECT_ROOT / "data" / "data"
OCR_CASES_PATH = PROJECT_ROOT / "benchmark_ocr_cases.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "finetuning"
OUTPUT_FILE = OUTPUT_DIR / "forensic_augmented_dataset_v2.jsonl"

def normalize_name(name):
    if not name: return ""
    return re.sub(r'[^a-z0-9]', '', name.lower())

def load_csv(path):
    if not path.exists():
        print(f"Warning: {path} not found.")
        return []
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def build_forensic_dataset():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Loading regulatory databases for forensic cross-referencing...")
    prop65 = load_csv(RAW_DATA_ROOT / "prop65_full_clean.csv")
    eu_food = load_csv(RAW_DATA_ROOT / "eu_food_additives.csv")
    iarc = load_csv(RAW_DATA_ROOT / "who_iarc_cancer_risk_list.csv")
    fda_cos = load_csv(RAW_DATA_ROOT / "fda_cosmetics_prohibited_restricted.csv")
    
    # Simple Indexing
    p65_names = {normalize_name(row['substance_name']): row for row in prop65}
    eu_db = {normalize_name(row['substance_name']): row for row in eu_food}
    iarc_db = {normalize_name(row['substance_name']): row for row in iarc}
    fda_db = {normalize_name(row['substance_name']): row for row in fda_cos}
    
    if not OCR_CASES_PATH.exists():
        print("Error: benchmark_ocr_cases.json not found.")
        return
        
    cases = json.loads(OCR_CASES_PATH.read_text())
    dataset = []
    
    print(f"Analyzing {len(cases)} verified OCR cases for global regulatory signals...")
    
    for case in cases:
        case_id = case["id"]
        # Join all expected strings as the "raw verified text"
        raw_text = " ".join(case.get("expected_strings", []))
        norm_text = normalize_name(raw_text)
        
        found_signals = defaultdict(list)
        
        # Cross-reference against all databases
        for name, row in p65_names.items():
            if len(name) > 5 and name in norm_text:
                found_signals["Prop 65"].append(row)
                
        for name, row in eu_db.items():
            if len(name) > 5 and name in norm_text:
                found_signals["EU Food"].append(row)
                
        for name, row in iarc_db.items():
            if len(name) > 5 and name in norm_text:
                found_signals["WHO IARC"].append(row)
                
        for name, row in fda_db.items():
            if len(name) > 5 and name in norm_text:
                found_signals["FDA Cosmetic"].append(row)

        if found_signals:
            # We found a case with forensic matches!
            sources_count = len(found_signals)
            
            context = f"Product Case: {case_id}\n"
            context += f"Verified Transcription Snippet: {raw_text[:200]}...\n"
            context += "Regulatory Matches Found:\n"
            
            for source, matches in found_signals.items():
                m = matches[0]
                context += f"- {source}: {m.get('substance_name')} is {m.get('regulatory_status', 'Listed')}. Basis: {m.get('hazard_basis', 'N/A')}\n"
            
            # Build Reasoning: Forensic Auditor
            verdict = f"Forensic Analysis for {case_id}:\n"
            
            has_p65 = "Prop 65" in found_signals
            if not has_p65:
                verdict += "This product is NOT flagged by California Prop 65, however, international forensic data reveals concerns. "
            else:
                verdict += "This product carries a Prop 65 signal, which is corroborated by other global sources. "
                
            if "EU Food" in found_signals:
                verdict += f"The EU Food Additives database identifies {found_signals['EU Food'][0]['substance_name']} as {found_signals['EU Food'][0]['regulatory_status']}. "
            
            if "WHO IARC" in found_signals:
                verdict += f"The WHO IARC cancer risk list classifies one or more ingredients in Group {found_signals['WHO IARC'][0]['regulatory_status']}. "

            verdict += "\nForensic Verdict: "
            if sources_count >= 2:
                verdict += "HIGH PRIORITY OVERLAP. Multiple global regulatory bodies have flagged ingredients in this product."
            else:
                verdict += "REGIONAL SIGNAL. Regional safety rules apply, but international consensus is limited."

            dataset.append({
                "instruction": "Perform a forensic multi-jurisdictional safety audit on this product based on its literal label transcription.",
                "input": context.strip(),
                "output": verdict.strip()
            })

    print(f"Writing {len(dataset)} forensic augmented pairs to {OUTPUT_FILE}...")
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for entry in dataset:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    build_forensic_dataset()
