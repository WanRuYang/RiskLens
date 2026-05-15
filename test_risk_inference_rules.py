from __future__ import annotations

from product_risk_formatter import risk_output_from_api_result


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
    assert "does not mean the oil itself is toxic" in oil["dose_context"]


def test_potato_chips_fried_in_vegetable_oil_flag_acrylamide_and_refined_oil_pathway() -> None:
    output = _output(
        "Potato chips fried in vegetable oil",
        "Potatoes, vegetable oil, sea salt",
        "food",
    )
    acrylamide = _risk(output, "Acrylamide")
    assert acrylamide["confidence_level"] == "likely"
    assert acrylamide["detection_basis"] == "processing derivative"


def test_infant_formula_with_palm_oil_adds_sensitive_group_context() -> None:
    output = _output(
        "Infant formula with palm oil",
        "Lactose, palm oil, whey protein concentrate",
        "food",
    )
    oil = _risk(output, "Glycidyl")
    assert oil["caution_level"] == "avoid for sensitive groups"
    assert "infants/children" in oil["sensitive_groups"]


def test_plastic_food_container_uses_packaging_contact_material_basis() -> None:
    output = _output("Plastic food container", "", "kitchen storage")
    phthalates = _risk(output, "Phthalates")
    assert phthalates["identification_method"] == "packaging/contact material"
    assert phthalates["detection_basis"] == "packaging/contact material"
    assert "confirmation requires" in phthalates["dose_context"].lower()


def test_pvc_shower_curtain_is_likely_phthalate_pathway() -> None:
    output = _output("PVC shower curtain", "", "bathroom product")
    phthalates = _risk(output, "Phthalates")
    assert phthalates["confidence_level"] == "likely"
    assert phthalates["caution_level"] == "avoid for sensitive groups"


def test_non_stick_frying_pan_flags_pfas_material_inference() -> None:
    output = _output("Non-stick frying pan with PTFE coating", "", "cookware")
    pfas = _risk(output, "PFAS")
    assert pfas["identification_method"] == "packaging/contact material"
    assert pfas["confidence_level"] == "explicit"


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


if __name__ == "__main__":
    test_cookies_with_vegetable_oil_use_process_language_not_toxic_oil_claim()
    test_potato_chips_fried_in_vegetable_oil_flag_acrylamide_and_refined_oil_pathway()
    test_infant_formula_with_palm_oil_adds_sensitive_group_context()
    test_plastic_food_container_uses_packaging_contact_material_basis()
    test_pvc_shower_curtain_is_likely_phthalate_pathway()
    test_non_stick_frying_pan_flags_pfas_material_inference()
    test_grease_resistant_microwave_popcorn_bag_flags_packaging_pfas()
    test_metal_can_flags_bpa_can_lining_pathway_without_calling_metal_toxic()
    test_bpa_free_can_keeps_can_lining_note_low_confidence()
    test_corn_syrup_candy_is_metabolic_not_regulatory_carcinogen_claim()
    test_smoked_red_meat_flags_pah_nitrosamine_pathway()
    test_childrens_soft_plastic_toy_flags_sensitive_phthalate_pathway()
    test_eu_strict_material_examples_are_inferred_cautiously()
    print("risk inference rules: ok")
