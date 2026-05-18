from __future__ import annotations

import json

from product_risk_formatter import (
    build_product_risk_output,
    detected_risk_from_chemical_match,
    process_derived_risk,
    surfactant_risks_from_ingredients,
)


def run_examples() -> dict[str, object]:
    ingredient_risk = detected_risk_from_chemical_match(
        {
            "chemical_id": "chem_red_3",
            "preferred_name": "FD&C Red No. 3",
            "matched_text": "Red 3",
        },
        ingredients_text="Sugar, Corn Syrup, Citric Acid, Natural Flavor, Red 3",
        regulatory_rows=[
            {
                "chemical_id": "chem_red_3",
                "preferred_name": "FD&C Red No. 3",
                "source_authority": "FDA",
                "regulatory_status": "Color additive subject to FDA restrictions and updates",
                "hazard_basis": "cancer concern in animal studies",
                "citation_url": "https://www.fda.gov/food/color-additives-information-consumers/color-additives-foods",
            },
            {
                "chemical_id": "chem_red_3",
                "preferred_name": "FD&C Red No. 3",
                "source_authority": "OEHHA",
                "regulatory_status": "Listed under California Proposition 65",
                "hazard_basis": "cancer",
                "citation_url": "https://oehha.ca.gov/proposition-65/proposition-65-list",
            },
        ],
    )
    process_risk = process_derived_risk(
        "Acrylamide",
        process_clue="roasted coffee / high-temperature roasting",
        source_rows=[
            {
                "source_authority": "IARC",
                "regulatory_status": "Hazard classification",
                "hazard_basis": "probably carcinogenic to humans",
                "citation_url": "https://monographs.iarc.who.int/",
            },
            {
                "source_authority": "OEHHA",
                "regulatory_status": "Listed under California Proposition 65",
                "hazard_basis": "cancer",
                "citation_url": "https://oehha.ca.gov/proposition-65/proposition-65-list",
            },
        ],
    )
    return build_product_risk_output(
        product_name="Example candy and roasted coffee screening",
        product_category="food",
        analysis_basis=["ingredients", "product category", "processing method"],
        identified_risks=[ingredient_risk, process_risk],
        ingredient_material_status="known from ingredient/material text",
        notable_uncertainties=[
            "No measured dose is available from the product label.",
            "Process-derived compounds are not directly listed ingredients.",
        ],
    )


def test_weighted_evidence_fields_are_emitted() -> None:
    output = run_examples()
    risks = output["identified_risks"]
    assert risks
    assert all("evidence_source" in risk for risk in risks)
    assert all("route_relevance" in risk for risk in risks)
    assert all("exposure_likelihood" in risk for risk in risks)
    assert all("population_factor" in risk for risk in risks)
    assert all("risk_points" in risk for risk in risks)


def run_surfactant_example() -> dict[str, object]:
    ingredients = (
        "Water, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Fragrance, "
        "PEG-40 Hydrogenated Castor Oil, Nonylphenol Ethoxylate"
    )
    risks = surfactant_risks_from_ingredients(
        ingredients,
        product_category="household cleaner / spray",
        warning_text="Use with ventilation. Avoid eye contact.",
    )
    return build_product_risk_output(
        product_name="Example surfactant-containing cleaner",
        product_category="household cleaner",
        analysis_basis=["ingredients", "product category"],
        identified_risks=risks,
        ingredient_material_status="known from ingredient/material text",
        notable_uncertainties=[
            "Surfactant family rules are screening signals. Actual residual contaminant levels require lab testing or supplier disclosure."
        ],
    )


if __name__ == "__main__":
    print(json.dumps({"general_example": run_examples(), "surfactant_example": run_surfactant_example()}, indent=2, ensure_ascii=False))
