# Hazardly Score UI

The Hazardly Score is a UI-rendered A-E score bar inspired by Nutri-Score, but it is not a nutrition score.

## Scope

The main score covers only chemical, material, contaminant, additive, warning, packaging/contact-material, and process-derived exposure signals.

It does not include general nutrition quality such as sugar, sodium, calories, saturated fat, or overall diet quality. Food-only nutrition concerns are displayed separately as `Food flags` inside the sibling `Hazardly Flags` card.

## Grades

- `A`: Low concern. No major risky ingredients, materials, contaminants, additives, or warning signals found from supported sources.
- `B`: Mild concern. Minor caution signals may exist, but likely exposure is low under normal use.
- `C`: Moderate concern. Contains or may involve signals that deserve caution, especially with frequent use.
- `D`: High concern. Contains one or more stronger chemical, material, contaminant, additive, or process-derived risk signals.
- `E`: Very high concern. Contains prominent or high-exposure risk signals; avoid frequent use and consider safer alternatives.

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
- Food-only flags remain separate from the A-E Hazardly Score.

Run:

```bash
/Users/adelie/Projects/gemma4good/.venv/bin/python -B /Users/adelie/Projects/gemma4good/test_hazardly_score.py
```
