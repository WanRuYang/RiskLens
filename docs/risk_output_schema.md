# Product Risk Output Schema

The app uses `product_risk_formatter.py` to create a JSON-compatible risk-screening object from detected product risks and source matches. This object is intended for both the local Gemma4 final-answer prompt and client rendering.

## Schema

```json
{
  "product_summary": {
    "product_name": "",
    "product_category": "",
    "analysis_basis": ["ingredients", "product category", "processing method"],
    "ingredient_material_status": "known from ingredient/material text | unknown; screening is inferred from product name and category",
    "overall_risk_level": "low | moderate | high | uncertain",
    "overall_recommendation": ""
  },
  "identified_risks": [
    {
      "chemical_name": "",
      "identification_method": "listed ingredient | likely process-derived | category-based risk | packaging/contact material",
      "detection_basis": "ingredient | product name | product category | processing derivative | packaging/contact material",
      "evidence_from_product": "",
      "dose_context": "",
      "risk_sources": [
        {
          "source": "FDA | WHO/IARC | EU/EFSA/ECHA | CA Prop 65 | EPA",
          "is_listed_or_warned": true,
          "risk_reason": "",
          "source_summary": "",
          "citation_url": ""
        }
      ],
      "consumer_explanation": "",
      "signal_type": "chemical_process | regulatory | contaminant | material_safety | confirmed_hazardous_ingredient | nutrition | allergen | ingredient_note | serving_size_note | general_product_info",
      "severity": "info | low | moderate | high | critical",
      "evidence_source": "lab_result | product_warning | recall_or_enforcement | food_regulatory_restriction | label_ingredient | process_inference | packaging_inference | category_prior | regulatory_list | nutrition_label | allergen_label | general_info",
      "route_relevance": "none | uncertain | food_or_oral",
      "exposure_likelihood": "theoretical | inferred | direct_unknown_dose | likely_meaningful | measured",
      "population_factor": "general_population | infant_child_pregnancy_targeted",
      "score_impact": "none | low | medium | high",
      "risk_points": 0.0,
      "caution_level": "low concern | use with caution | limit frequent exposure | avoid for sensitive groups | avoid if allergic",
      "user_recommendation": "low concern | use with caution | limit frequent exposure | avoid for sensitive groups | avoid if allergic",
      "sensitive_groups": ["children", "pregnant people", "people with allergies", "frequent users"],
      "confidence": "low | medium | high | explicit | likely | possible | weak inference | measured",
      "confidence_level": "explicit | likely | possible | weak inference | low | medium | high | measured"
    }
  ],
  "notable_uncertainties": [""],
  "final_consumer_guidance": "",
  "disclaimer": "This analysis is for informational screening only and does not determine whether a product is legally unsafe or medically harmful. Actual risk depends on dose, frequency, individual sensitivity, and exposure route."
}
```

The API also exposes a normalized shared score object for web and phone rendering:

```json
{
  "total_risk_points": 0.0,
  "flags": [
    {
      "label": "",
      "type": "chemical_process | regulatory | contaminant | material_safety | confirmed_hazardous_ingredient | nutrition | allergen | ingredient_note | serving_size_note | general_product_info",
      "severity": "info | low | moderate | high | critical",
      "confidence": "weak | possible | likely | confirmed | measured",
      "evidence_source": "lab_result | product_warning | recall_or_enforcement | food_regulatory_restriction | label_ingredient | process_inference | packaging_inference | category_prior | regulatory_list | nutrition_label | allergen_label | general_info",
      "route_relevance": "none | uncertain | food_or_oral",
      "exposure_likelihood": "theoretical | inferred | direct_unknown_dose | likely_meaningful | measured",
      "population_factor": "general_population | infant_child_pregnancy_targeted",
      "score_impact": "none | low | medium | high",
      "risk_points": 0.0,
      "reason": ""
    }
  ]
}
```

Only `chemical_process`, `regulatory`, `contaminant`, `material_safety`, and `confirmed_hazardous_ingredient` may affect the A-E Hazardly Score. Nutrition, allergens, ingredient notes, serving-size notes, and general product information are display-only flags and use `score_impact: "none"`.

The score uses a weighted evidence model rather than treating all list matches as equal:

`risk_points = severity x evidence_strength x exposure_likelihood x route_relevance x population_factor`

The evidence hierarchy runs from measured lab exceedance, to product-specific warning/recall, to food-specific restriction, to confirmed ingredient, to process inference, to packaging inference, to category prior. Route relevance filters matter: a non-food-relevant list match must not be scored as a direct food risk.

## Interpretation Rules

- Listed ingredients are product-specific only when matched directly from parsed ingredient/material/warning text.
- Process-derived compounds are marked as `likely process-derived` and use uncertain dose language.
- Category-only model outputs are not treated as confirmed chemicals in the product.
- Product/material clues are routed through deterministic pathway rules before Gemma writes the final answer. Gemma should identify facts such as `cookie`, `fried`, `non-stick`, `PVC`, or `composite wood`; the formatter decides the cautious risk pathway.
- Broad ingredients are not labeled toxic by default. For example, `corn syrup` is treated as a nutrition/metabolic context, while `vegetable oil` or `palm oil` can create a possible refined-oil contaminant pathway such as glycidyl esters or 3-MCPD esters.
- Generic baked-food acrylamide is a `possible`, `moderate`, low-impact process signal. Generic `vegetable oil` creates a weak/low-impact refined-oil note; specific palm-oil clues may raise that note to moderate severity with low-to-medium impact.
- Baked, fried, roasted, smoked, cured, and grilled product clues are treated as possible process-derived pathways, not confirmed measured concentrations.
- Plastic packaging, soft PVC/vinyl, non-stick/PTFE, grease-resistant packaging, composite wood, dyed textiles, and flame-retardant/foam clues are treated as material or contact-pathway inferences.
- Metal cans and can-lining clues are treated as possible packaging/contact-material pathways for BPA or related bisphenol lining chemistry. The formatter should not claim the metal can itself is toxic, and a `BPA-free` claim should lower the confidence and caution level unless another disclosed chemical is present.
- Surfactants are not treated as automatically hazardous. The formatter separates:
- Ethoxylated surfactants such as `PEG-`, `PPG-`, `polysorbate`, `sodium laureth sulfate`, `laureth-`, `ceteareth-`, `steareth-`, `oleth-`, and related names as possible 1,4-dioxane residual-contaminant signals, not confirmed ingredients.
- Alkylphenol ethoxylates such as `NPE`, `OPE`, `APEO`, nonylphenol ethoxylate, and octylphenol ethoxylate as environmental/endocrine concern signals.
- Common irritant surfactants such as `SLS`, `SLES`, cocamidopropyl betaine, benzalkonium chloride, and quaternary ammonium compounds as irritation/allergy/sensitization signals, not carcinogenic warnings unless a specific listed contaminant is detected.
- If no risk is found, the formatter returns: `No major risk warnings were identified from the available ingredient and category information.`
- The formatter does not make medical or legal determinations.

## Example

Run:

```bash
/Users/adelie/Projects/gemma4good/.venv/bin/python -B test_risk_output_formatter.py
/Users/adelie/Projects/gemma4good/.venv/bin/python -B test_risk_inference_rules.py
```

The examples include listed ingredient risks, surfactant family handling, process-derived food risks, packaging/contact-material risks, and false-positive controls such as corn syrup not being treated as a regulatory carcinogen.
