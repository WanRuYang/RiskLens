import sys
import json
from pathlib import Path
from mlx_engine import run_scribe_agent, run_classifier_agent
from safety_lookup import SafetyKnowledgeBase
from risklens_score import risklens_score_from_api_result
import re

# Setup paths
IMG_PATHS = [
    "/Users/adelie/Desktop/Screenshot 2026-05-16 at 10.50.46 PM.png",
    "/Users/adelie/Desktop/Screenshot 2026-05-16 at 11.14.09 PM.png"
]

def debug_flow():
    print("=== STAGE 1: OCR (Scribe Agent) ===")
    # 1. Run OCR
    raw_ocr = run_scribe_agent(IMG_PATHS)
    print(f"RAW OCR OUTPUT:\n{raw_ocr}\n")

    print("=== STAGE 2: CLASSIFICATION & STRUCTURING ===")
    # 2. Structure the data
    structured = run_classifier_agent(raw_ocr)
    product_name = structured.get("product_name", "Unknown Skittles")
    ingredients = structured.get("ingredient_text", "")
    print(f"PRODUCT NAME: {product_name}")
    print(f"EXTRACTED INGREDIENTS:\n{ingredients}\n")

    print("=== STAGE 3: FORENSIC MATCHING (Knowledge Base) ===")
    # 3. Knowledge Base Lookup (Testing the fix I just made)
    kb = SafetyKnowledgeBase()
    
    # Check if we can find the specific culprits in aliases
    print("Checking internal KB aliases for Red 40...")
    red40_aliases = [a for a in kb.chemical_aliases if "red 40" in a[0]]
    print(f"Found {len(red40_aliases)} aliases matching 'red 40'")
    
    matches = kb.match_chemicals(product_name, ingredients)
    print(f"MATCHED CHEMICALS ({len(matches)}):")
    for m in matches:
        print(f" - {m.preferred_name} (Alias: {m.matched_alias}, Score: {m.match_score})")
    
    print("\n=== STAGE 4: RETRIEVAL & EVIDENCE ===")
    retrieval = kb.retrieve(product_name, ingredients, region="California, USA")
    
    direct_ev = retrieval.get("regulatory_evidence", [])
    supp_ev = retrieval.get("supplemental_regulatory_evidence", [])
    
    print(f"DIRECT EVIDENCE ROWS: {len(direct_ev)}")
    print(f"SUPPLEMENTAL EVIDENCE ROWS: {len(supp_ev)}")
    
    # Look for EU warnings in evidence
    eu_warnings = [r for r in direct_ev + supp_ev if "activity and attention" in (r.get("hazard_basis") or "").lower()]
    print(f"EU CHILD-BEHAVIOR WARNINGS FOUND: {len(eu_warnings)}")
    for w in eu_warnings[:2]:
        print(f" - Source: {w.get('source_authority')}, Status: {w.get('regulatory_status')}")

    print("\n=== STAGE 5: SCORING ===")
    # 5. Calculate Score
    # We need to format the result like an API response for the scorer
    api_sim = {
        "chemical_matches": [m.__dict__ for m in matches],
        "direct_regulatory_evidence": direct_ev,
        "supplemental_regulatory_evidence": supp_ev,
        "warning_interpretations": retrieval.get("warning_interpretations", []),
        "inferred_category": {"product_use_category": "food", "material_subcategory": "ingestible_food_matrix"},
        "ingredients_text": ingredients,
        "product_name": product_name
    }
    
    score_result = risklens_score_from_api_result(api_sim)
    print(f"FINAL RISKLENS SCORE: {score_result.score}")
    print(f"TOTAL RISK POINTS: {score_result.totalRiskPoints}")
    print(f"FLAGS GENERATED: {len(score_result.flags)}")
    for f in score_result.flags:
        print(f" - Flag: {f.label}, Points: {f.riskPoints}, Severity: {f.severity}")

if __name__ == "__main__":
    debug_flow()
