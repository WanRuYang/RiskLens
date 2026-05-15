# Hazardly Score UI

The Hazardly Score is a UI-rendered A-E score bar inspired by Nutri-Score, but it is not a nutrition score.

## Scope

The main score covers only chemical, material, contaminant, additive, warning, packaging/contact-material, and process-derived exposure signals.

It does not include general nutrition quality such as sugar, sodium, calories, saturated fat, or overall diet quality. Food-only nutrition concerns are displayed separately as `Food flags`.

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

The component renders below the chat window as normal app UI. It is intentionally not inserted into the LLM response text.

Run:

```bash
/Users/adelie/Projects/gemma4good/.venv/bin/python -B /Users/adelie/Projects/gemma4good/test_hazardly_score.py
```
