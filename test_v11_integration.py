import json
import time
from pathlib import Path
from mlx_engine import (
    run_scribe_agent,
    run_classifier_agent,
    run_search_agent,
    run_editor_agent,
    verify_category_vlm,
    run_feedback_agent
)

PROJECT_ROOT = Path(__file__).resolve().parent
TEST_IMAGE = str(PROJECT_ROOT / "benchmark_images/weee_001/front.png")

def run_integration_test():
    print("=== End-to-End Integration Test (v11.0 Agentic Flow) ===")
    
    # 1. Vision Stage
    print("\n1. Testing Scribe Agent (Vision)...")
    ocr_text = run_scribe_agent([TEST_IMAGE], mode="hybrid")
    assert ocr_text, "Scribe Agent failed to extract text."
    print(f"   Success! Extracted {len(ocr_text)} characters.")
    
    # 2. Logic Stage
    print("\n2. Testing Classifier Agent (Logic)...")
    classification = run_classifier_agent(ocr_text)
    assert "product_use_category" in classification, "Classifier failed to categorize."
    print(f"   Success! Categorized as: {classification['product_use_category']}")
    
    # 3. Verification Stage
    print("\n3. Testing Autonomous Self-Verification...")
    vlm_verified = verify_category_vlm(classification['product_use_category'], [TEST_IMAGE])
    print(f"   Success! Self-Verification Pass: {vlm_verified}")
    
    # 4. Search Stage
    print("\n4. Testing Search Agent (Native Retrieval)...")
    search_data = {
        "product_name": classification.get("product_name", "Test"),
        "ingredient_text": classification.get("ingredient_text", ""),
        "region": "California, USA"
    }
    api_result = run_search_agent(search_data)
    assert "regulatory_evidence" in api_result, "Search Agent failed to retrieve data."
    print(f"   Success! Found {len(api_result['regulatory_evidence'])} regulatory matches.")
    
    # 5. Reporting Stage
    print("\n5. Testing Editor Agent (Forensic Report)...")
    report = run_editor_agent(classification, api_result)
    assert "##" in report, "Editor failed to generate structured report."
    print("   Success! Forensic report synthesized.")
    
    # 6. Feedback Stage
    print("\n6. Testing Consultant Agent (Feedback Loop)...")
    query = "Why is this product in the food category?"
    feedback = run_feedback_agent(query, {"api_result": api_result})
    assert "response" in feedback, "Consultant Agent failed to provide feedback."
    print("   Success! Consultant provided expert reasoning.")
    
    print("\n" + "="*50)
    print(" END-TO-END INTEGRATION TEST PASSED")
    print("="*50)

if __name__ == "__main__":
    try:
        run_integration_test()
    except Exception as e:
        print(f"\n[FAILURE] Integration Test Failed: {e}")
        exit(1)
