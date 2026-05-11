# Product Label Classifier

This artifact is trained from weak labels derived from Prop 65 notices and regulatory evidence tables.
It should be used as a candidate-label/routing model, not as regulatory truth.

- Model artifact: `/Users/adelie/Projects/gemma4good/models/product_label_classifier/product_label_classifier.joblib`
- Model type: TF-IDF features + balanced logistic regression
- Primary use: predict product category, exposure pathway, concern family, and regulatory risk label before Gemma writes the final user-facing explanation.

## Evaluation

| Task | Rows | Accuracy | Macro F1 | Weighted F1 |
| --- | ---: | ---: | ---: | ---: |
| product_category | 22064 | 0.9721 | 0.9616 | 0.9722 |
| exposure_pathway | 17837 | 0.9658 | 0.7986 | 0.9683 |
| concern_family | 17837 | 0.9922 | 0.9735 | 0.9923 |
| risk_label | 1683 | 0.7482 | 0.8073 | 0.7518 |

## Caveats

- These metrics are against held-out weak labels, not manually verified ground truth.
- High scores mean the model learned the labeling rules consistently; they do not prove the rules are complete.
- Low-confidence or `unknown` Prop 65 notice rows are excluded from most training tasks.
- For food, the pathway label is especially important because concerns can come from declared ingredients, processing byproducts, raw-material contaminants, or packaging/contact materials.