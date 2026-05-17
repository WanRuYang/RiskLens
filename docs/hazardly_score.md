# Hazardly Score UI

The Hazardly Score is a UI-rendered A-E score bar inspired by Nutri-Score, but it is not a nutrition score.

## Scope

The main score covers only chemical/process, regulatory, contaminant, material-safety, and confirmed hazardous-ingredient signals.

It does not include general nutrition quality such as sugar, sodium, calories, saturated fat, allergens, serving-size notes, or overall diet quality. Food-only nutrition concerns are displayed as white `Nutrition & ingredient notes` chips beside pink `Processing-related signals` chips inside the sibling `Hazardly Flags` card.

Shared flag schema:

```json
{
  "label": "Possible acrylamide formation",
  "type": "chemical_process",
  "severity": "moderate",
  "confidence": "possible",
  "evidence_source": "process_inference",
  "route_relevance": "food_or_oral",
  "exposure_likelihood": "inferred",
  "population_factor": "general_population",
  "score_impact": "low",
  "risk_points": 0.5,
  "reason": "Possible acrylamide formation due to baked / high-temperature carbohydrate-rich food."
}
```

Only `chemical_process`, `regulatory`, `contaminant`, `material_safety`, and `confirmed_hazardous_ingredient` may affect the A-E score. `nutrition`, `allergen`, `ingredient_note`, `serving_size_note`, and `general_product_info` always use `score_impact: "none"`.

Database-backed regulatory signals can affect the score when they are both direct and product-relevant. For example, a label-confirmed synthetic dye that maps to an EU warning-label requirement is treated as a regulatory signal, while the explanation still states that `authorized with conditions` is not the same as a blanket ban.

Final grade guardrails are applied after weighted points:

- `A` is allowed only when no score-relevant flag has `risk_points > 0`.
- One low-impact score-relevant flag floors the result at `B`.
- Two or more independent low-impact flags, or one medium-impact flag, floor the result at `C`.
- One high-impact confirmed/regulatory flag floors the result at `D`.
- Measured exceedance, recall/enforcement, or multiple high-impact confirmed flags floor the result at `E`.

## Weighted Evidence Model

Hazardly uses positive weighted points, not a simple keyword penalty:

`riskPoints = severity x evidenceStrength x exposureLikelihood x routeRelevance x populationFactor`

- Severity: `low=1`, `moderate=2`, `high=3`, `critical=4`
- Evidence strength: `weak=0.25`, `possible=0.50`, `likely=0.75`, `confirmed=1.00`, `measured=1.25`
- Exposure likelihood: `theoretical=0.25`, `inferred=0.50`, `direct_unknown_dose=0.75`, `likely_meaningful=1.00`, `measured=1.00`
- Route relevance: `none=0`, `uncertain=0.5`, `food_or_oral=1.0`
- Population factor: `general_population=1.0`, `infant_child_pregnancy_targeted=1.25`

If route relevance is `none`, points are always `0`. Nutrition, allergens, ingredient notes, serving-size notes, and general product info are display-only flags with `0` points.

Evidence is ranked from strongest to weakest:

1. product-specific lab result / measured exceedance
2. product-specific regulatory warning, recall, or enforcement
3. food-specific regulatory ban or restriction
4. confirmed label ingredient with active food-safety concern
5. robust process clue
6. packaging/material clue supported by product metadata
7. category-only inference
8. authorized nutrient or common additive with no active food-specific concern

## Grades

- `A` (`0-0.75`): Low chemical/process concern. No meaningful concern survived relevance filters.
- `B` (`>0.75-1.75`): Minor chemical/process concern. One weak or possible concern; mostly informational.
- `C` (`>1.75-3.0`): Moderate chemical/process concern. One meaningful but not decisive concern, or several smaller concerns.
- `D` (`>3.0-4.5`): High chemical/process concern. Strong food-relevant concern or multiple moderate/high signals.
- `E` (`>4.5`): Very high chemical/process concern. Measured exceedance, direct regulatory warning, infant-targeted high-priority concern, or multiple serious signals.

## Implementation

- Component: `/Users/adelie/Projects/gemma4good/hazardly_score.py`
- Gradio integration: `/Users/adelie/Projects/gemma4good/app.py`
- Regression test: `/Users/adelie/Projects/gemma4good/test_hazardly_score.py`

The web result stack is:

1. Hazardly Score
2. Hazardly Flags
3. Scrollable Result explanation
4. Submit feedback

The score component and flag component render as normal app UI. They are intentionally not inserted into the LLM response text.

## Nutrition flag thresholds

- `High sodium` requires label evidence of at least `20% DV` or about `460 mg` sodium per serving.
- The presence of the word `sodium` or `salt` alone is not enough to create a `High sodium` flag; this prevents low-sodium false positives.
- Food-only flags remain separate from the A-E Hazardly Score, and Nutrition Facts are optional for scoring.
- Common snack signals are calibrated conservatively: generic baked cookies usually create a `1.0`-point possible acrylamide signal and land at least at `B`; generic vegetable oil alone is display-only with `0` points; palm-oil clues can add about `1.0` point, so cookies with both acrylamide and palm-oil process signals usually land at `C`, not `D`.

Run:

```bash
/Users/adelie/Projects/gemma4good/.venv/bin/python -B /Users/adelie/Projects/gemma4good/test_hazardly_score.py
```
