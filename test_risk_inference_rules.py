from __future__ import annotations

from product_risk_formatter import risk_output_from_api_result
from safety_lookup import SafetyKnowledgeBase


def _output(product_name: str, ingredients: str = "", category: str = "") -> dict:
    return risk_output_from_api_result(
        {
            "inferred_category": {
                "product_use_category": category,
                "material_subcategory": "",
            },
            "chemical_matches": [],
            "direct_regulatory_evidence": [],
            "category_level_regulatory_evidence": [],
        },
        product_name=product_name,
        ingredients_text=ingredients,
    )


def _names(output: dict) -> list[str]:
    return [risk["chemical_name"] for risk in output["identified_risks"]]


def _risk(output: dict, contains: str) -> dict:
    for risk in output["identified_risks"]:
        if contains.lower() in risk["chemical_name"].lower():
            return risk
    raise AssertionError(f"Missing risk containing {contains!r}: {_names(output)}")


def test_cookies_with_vegetable_oil_use_process_language_not_toxic_oil_claim() -> None:
    output = _output(
        "Chocolate chip cookies",
        "Wheat flour, sugar, vegetable oil, chocolate chips",
        "food",
    )
    names = " ".join(_names(output)).lower()
    assert "glycidyl" in names
    assert "acrylamide" in names
    oil = _risk(output, "Glycidyl")
    assert oil["identification_method"] == "likely process-derived"
    assert oil["detection_basis"] == "processing derivative"
    assert oil["confidence_level"] == "weak inference"
    assert oil["signal_type"] == "contaminant"
    assert oil["score_impact"] == "none"
    assert "does not mean the oil itself is toxic" in oil["dose_context"]


def test_potato_chips_fried_in_vegetable_oil_flag_acrylamide_and_refined_oil_pathway() -> None:
    output = _output(
        "Potato chips fried in vegetable oil",
        "Potatoes, vegetable oil, sea salt",
        "food",
    )
    acrylamide = _risk(output, "Acrylamide")
    assert acrylamide["confidence_level"] == "likely"
    assert acrylamide["severity"] == "moderate"
    assert acrylamide["score_impact"] == "low"
    assert acrylamide["detection_basis"] == "processing derivative"


def test_infant_formula_with_palm_oil_adds_sensitive_group_context() -> None:
    output = _output(
        "Infant formula with palm oil",
        "Lactose, palm oil, whey protein concentrate",
        "food",
    )
    oil = _risk(output, "Glycidyl")
    assert oil["caution_level"] == "avoid for sensitive groups"
    assert oil["signal_type"] == "contaminant"
    assert oil["score_impact"] == "medium"
    assert "infants/children" in oil["sensitive_groups"]


def test_plastic_food_container_uses_packaging_contact_material_basis() -> None:
    output = _output("Plastic food container", "", "kitchen storage")
    phthalates = _risk(output, "Phthalates")
    assert phthalates["identification_method"] == "packaging/contact material"
    assert phthalates["detection_basis"] == "packaging/contact material"
    assert phthalates["signal_type"] == "material_safety"
    assert "confirmation requires" in phthalates["dose_context"].lower()


def test_pvc_shower_curtain_is_likely_phthalate_pathway() -> None:
    output = _output("PVC shower curtain", "", "bathroom product")
    phthalates = _risk(output, "Phthalates")
    assert phthalates["confidence_level"] == "likely"
    assert phthalates["caution_level"] == "avoid for sensitive groups"


def test_non_stick_frying_pan_flags_ptfe_condition_without_claiming_pfas_presence() -> None:
    output = _output("Non-stick frying pan with PTFE coating", "", "cookware")
    ptfe = _risk(output, "PTFE / nonstick coating")
    assert ptfe["identification_method"] == "packaging/contact material"
    assert ptfe["confidence_level"] == "explicit"
    assert "not PFOA/PFOS presence" in ptfe["dose_context"]


def test_grease_resistant_microwave_popcorn_bag_flags_packaging_pfas() -> None:
    output = _output("Grease-resistant microwave popcorn bag", "", "food packaging")
    pfas = _risk(output, "PFAS")
    assert pfas["detection_basis"] == "packaging/contact material"
    assert pfas["caution_level"] == "limit frequent exposure"


def test_metal_can_flags_bpa_can_lining_pathway_without_calling_metal_toxic() -> None:
    output = _output("Canned tomatoes in metal can", "Tomatoes, tomato juice, salt", "food")
    bpa = _risk(output, "BPA")
    assert bpa["identification_method"] == "packaging/contact material"
    assert bpa["detection_basis"] == "packaging/contact material"
    assert bpa["confidence_level"] == "possible"
    assert "Metal cans are not treated as hazardous by default" in bpa["dose_context"]
    assert "proof that this product contains or releases BPA" in bpa["consumer_explanation"]


def test_bpa_free_can_keeps_can_lining_note_low_confidence() -> None:
    output = _output("BPA-free canned beans in steel can", "Beans, water, salt", "food")
    can_lining = _risk(output, "Can-lining")
    assert can_lining["caution_level"] == "low concern"
    assert can_lining["confidence_level"] == "weak inference"
    assert "BPA itself is not inferred" in can_lining["dose_context"]


def test_corn_syrup_candy_is_metabolic_not_regulatory_carcinogen_claim() -> None:
    output = _output(
        "Gummy candy",
        "Corn syrup, sugar, gelatin, natural flavor",
        "food",
    )
    corn = _risk(output, "Added sugars")
    assert corn["detection_basis"] == "ingredient"
    assert corn["caution_level"] == "low concern"
    assert "not being labeled as a Prop 65, EPA, or EU carcinogenic chemical warning" in corn["consumer_explanation"]


def test_priority_overlay_adds_food_dye_aliases_to_retrieval_layer() -> None:
    kb = SafetyKnowledgeBase()
    matches = kb.match_chemicals(
        "Rainbow gummy candy",
        "Sugar, corn syrup, Red 40 Lake, E124, Carmoisine",
    )
    preferred_names = {match.preferred_name for match in matches}
    assert "Allura Red AC" in preferred_names
    assert "Ponceau 4R" in preferred_names
    assert "Azorubine / Carmoisine" in preferred_names


def test_priority_overlay_keeps_food_dye_evidence_in_data_layer() -> None:
    kb = SafetyKnowledgeBase()
    matches = kb.match_chemicals("Rainbow gummy candy", "Red 40")
    red40 = next(match for match in matches if match.preferred_name == "Allura Red AC")
    evidence = kb.evidence_by_chemical_id[red40.chemical_id]
    statuses = {row["regulatory_status"] for row in evidence}
    assert "Authorised with conditions; warning label required" in statuses
    assert "Permanently listed" in statuses


def test_smoked_red_meat_flags_pah_nitrosamine_pathway() -> None:
    output = _output("Smoked red meat sausage", "Beef, salt, spices", "food")
    risk = _risk(output, "PAHs")
    assert risk["detection_basis"] == "processing derivative"
    assert risk["confidence_level"] == "likely"


def test_childrens_soft_plastic_toy_flags_sensitive_phthalate_pathway() -> None:
    output = _output("Children's toy made of soft plastic", "", "toy")
    phthalates = _risk(output, "Phthalates")
    assert phthalates["caution_level"] == "avoid for sensitive groups"
    assert "children" in phthalates["sensitive_groups"]


def test_eu_strict_material_examples_are_inferred_cautiously() -> None:
    wood = _output("Composite wood nursery shelf", "", "furniture")
    formaldehyde = _risk(wood, "Formaldehyde")
    assert formaldehyde["confidence_level"] == "possible"
    assert "EPA" in [source["source"] for source in formaldehyde["risk_sources"]]

    textile = _output("Dyed textile costume", "", "textiles")
    azo = _risk(textile, "Azo")
    assert azo["confidence_level"] == "weak inference"
    assert azo["detection_basis"] == "product category"


def test_melamine_hot_soup_uses_contextual_material_logic() -> None:
    output = _output("Melamine bowl for hot soup", "", "food contact")
    melamine = _risk(output, "Melamine")
    assert melamine["identification_method"] == "packaging/contact material"
    assert melamine["caution_level"] == "limit frequent exposure"
    assert "hot, acidic" in melamine["consumer_explanation"]


def test_black_plastic_spatula_is_possible_contamination_not_confirmed_ingredient() -> None:
    output = _output("Black plastic spatula for frying", "", "cookware")
    black_plastic = _risk(output, "PBDEs")
    assert black_plastic["identification_method"] == "packaging/contact material"
    assert black_plastic["confidence_level"] == "possible"
    assert "not a confirmed ingredient list" in black_plastic["dose_context"]


def test_scratched_nonstick_pan_separates_ptfe_from_legacy_pfas_context() -> None:
    output = _output("Scratched nonstick Teflon pan", "", "cookware")
    ptfe = _risk(output, "PTFE / nonstick coating")
    assert ptfe["caution_level"] == "limit frequent exposure"
    assert "not PFOA/PFOS presence" in ptfe["dose_context"]


if __name__ == "__main__":
    test_cookies_with_vegetable_oil_use_process_language_not_toxic_oil_claim()
    test_potato_chips_fried_in_vegetable_oil_flag_acrylamide_and_refined_oil_pathway()
    test_infant_formula_with_palm_oil_adds_sensitive_group_context()
    test_plastic_food_container_uses_packaging_contact_material_basis()
    test_pvc_shower_curtain_is_likely_phthalate_pathway()
    test_non_stick_frying_pan_flags_ptfe_condition_without_claiming_pfas_presence()
    test_grease_resistant_microwave_popcorn_bag_flags_packaging_pfas()
    test_metal_can_flags_bpa_can_lining_pathway_without_calling_metal_toxic()
    test_bpa_free_can_keeps_can_lining_note_low_confidence()
    test_corn_syrup_candy_is_metabolic_not_regulatory_carcinogen_claim()
    test_priority_overlay_adds_food_dye_aliases_to_retrieval_layer()
    test_priority_overlay_keeps_food_dye_evidence_in_data_layer()
    test_smoked_red_meat_flags_pah_nitrosamine_pathway()
    test_childrens_soft_plastic_toy_flags_sensitive_phthalate_pathway()
    test_eu_strict_material_examples_are_inferred_cautiously()
    test_melamine_hot_soup_uses_contextual_material_logic()
    test_black_plastic_spatula_is_possible_contamination_not_confirmed_ingredient()
    test_scratched_nonstick_pan_separates_ptfe_from_legacy_pfas_context()
    print("risk inference rules: ok")
