from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import joblib


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "product_label_classifier" / "product_label_classifier.joblib"
DEFAULT_LINKAGE_PATH = PROJECT_ROOT / "data" / "derived" / "label_datasets" / "product_chemical_linkage.json"

CHEMICAL_FAMILY_RULES = [
    ("phthalates_plasticizers", ["phthalate", "dehp", "dinp", "dbp", "bbp", "didp"]),
    ("heavy_metals", ["lead", "cadmium", "arsenic", "mercury", "chromium"]),
    ("bisphenols", ["bisphenol", "bpa", "bps", "bpf"]),
    ("pfas", ["pfas", "pfoa", "pfos", "fluorinated"]),
    ("heat_generated_contaminants", ["acrylamide", "benz[a]anthracene", "benzo[a]pyrene", "nitroso", "nitrosamine"]),
    ("solvents_vocs", ["toluene", "benzene", "xylene", "formaldehyde", "acetaldehyde"]),
    ("pesticides", ["glyphosate", "chlorpyrifos", "malathion"]),
    ("food_additives", ["titanium dioxide", "benzoic", "sulfite", "sulphite", "bha", "bht"]),
]


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def _chemical_family_rule(text: str) -> str | None:
    normalized = _clean_text(text).lower()
    for family, terms in CHEMICAL_FAMILY_RULES:
        if any(term in normalized for term in terms):
            return family
    return None


def _load_linkage_rows(linkage_path: str | Path = DEFAULT_LINKAGE_PATH) -> list[dict[str, Any]]:
    path = Path(linkage_path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def build_feature_text(
    *,
    product_text: str = "",
    ingredient_text: str = "",
    material_text: str = "",
    chemical_text: str = "",
    warning_text: str = "",
    source_text: str = "",
    product_category: str = "",
    jurisdiction: str = "",
    regulatory_status: str = "",
    hazard_basis: str = "",
) -> dict[str, str]:
    """Build task-specific feature strings for the weak-label classifiers."""
    product_core = _clean_text(" ".join([product_text, ingredient_text, material_text, warning_text, source_text]))
    product_with_chem = _clean_text(" ".join([product_core, chemical_text]))
    regulatory_core = _clean_text(
        " ".join([chemical_text, product_category, jurisdiction, regulatory_status, hazard_basis, source_text])
    )
    return {
        "product_category": product_core,
        "exposure_pathway": product_with_chem,
        "concern_family": product_with_chem,
        "risk_label": regulatory_core,
    }


@dataclass
class ProductLabelPrediction:
    label: str
    confidence: float
    alternatives: list[dict[str, float]]


class ProductLabelClassifier:
    def __init__(self, artifact: dict[str, Any]) -> None:
        self.artifact = artifact
        self.models = artifact["models"]
        self.metadata = artifact.get("metadata", {})

    @classmethod
    def load(cls, model_path: str | Path = DEFAULT_MODEL_PATH) -> "ProductLabelClassifier":
        return cls(joblib.load(model_path))

    def predict(
        self,
        *,
        product_text: str = "",
        ingredient_text: str = "",
        material_text: str = "",
        chemical_text: str = "",
        warning_text: str = "",
        source_text: str = "",
        product_category: str = "",
        jurisdiction: str = "",
        regulatory_status: str = "",
        hazard_basis: str = "",
        top_k: int = 3,
    ) -> dict[str, ProductLabelPrediction]:
        features = build_feature_text(
            product_text=product_text,
            ingredient_text=ingredient_text,
            material_text=material_text,
            chemical_text=chemical_text,
            warning_text=warning_text,
            source_text=source_text,
            product_category=product_category,
            jurisdiction=jurisdiction,
            regulatory_status=regulatory_status,
            hazard_basis=hazard_basis,
        )
        predictions: dict[str, ProductLabelPrediction] = {}
        for task_name, model in self.models.items():
            text = features.get(task_name, "")
            if not text:
                continue
            probabilities = model.predict_proba([text])[0]
            classes = list(model.classes_)
            ranked = sorted(zip(classes, probabilities), key=lambda item: item[1], reverse=True)[:top_k]
            predictions[task_name] = ProductLabelPrediction(
                label=str(ranked[0][0]),
                confidence=round(float(ranked[0][1]), 4),
                alternatives=[{"label": str(label), "confidence": round(float(score), 4)} for label, score in ranked],
            )
        rule_family = _chemical_family_rule(" ".join([chemical_text, ingredient_text, material_text, warning_text]))
        if rule_family:
            previous = predictions.get("concern_family")
            alternatives = [{"label": rule_family, "confidence": 0.99}]
            if previous:
                alternatives.extend(item for item in previous.alternatives if item["label"] != rule_family)
            predictions["concern_family"] = ProductLabelPrediction(
                label=rule_family,
                confidence=0.99,
                alternatives=alternatives[:top_k],
            )
        return predictions

    def candidate_chemical_linkages(
        self,
        predictions: dict[str, ProductLabelPrediction],
        *,
        linkage_path: str | Path = DEFAULT_LINKAGE_PATH,
        top_k: int = 4,
        min_score: float = 0.6,
    ) -> list[dict[str, Any]]:
        category = predictions.get("product_category")
        pathway = predictions.get("exposure_pathway")
        family = predictions.get("concern_family")
        if not (category or pathway or family):
            return []

        category_label = category.label if category else ""
        pathway_label = pathway.label if pathway else ""
        family_label = family.label if family else ""
        category_conf = category.confidence if category else 0.0
        pathway_conf = pathway.confidence if pathway else 0.0
        family_conf = family.confidence if family else 0.0

        scored_rows: list[tuple[float, dict[str, Any]]] = []
        for row in _load_linkage_rows(linkage_path):
            score = 0.0
            if category_label and row.get("product_category_label") == category_label:
                score += 0.4 * category_conf
            if pathway_label and row.get("exposure_pathway_label") == pathway_label:
                score += 0.35 * pathway_conf
            if family_label and row.get("concern_family_label") == family_label:
                score += 0.3 * family_conf
            if score <= 0:
                continue
            if family_label and row.get("concern_family_label") != family_label and score < 0.5:
                continue
            support = min(float(row.get("total_notice_rows") or 0) / 500.0, 0.25)
            scored = round(score + support, 4)
            if scored < min_score:
                continue
            scored_rows.append((scored, row))

        results: list[dict[str, Any]] = []
        for score, row in sorted(scored_rows, key=lambda item: item[0], reverse=True)[:top_k]:
            results.append(
                {
                    "linkage_score": score,
                    "product_category_label": row.get("product_category_label"),
                    "exposure_pathway_label": row.get("exposure_pathway_label"),
                    "concern_family_label": row.get("concern_family_label"),
                    "total_notice_rows": row.get("total_notice_rows"),
                    "mean_label_confidence": row.get("mean_label_confidence"),
                    "top_chemicals": row.get("top_chemicals", [])[:5],
                    "example_products": row.get("example_products", [])[:3],
                    "usage_caveat": row.get("usage_caveat"),
                }
            )
        return results


def predict_product_labels(**kwargs: Any) -> dict[str, dict[str, Any]]:
    classifier = ProductLabelClassifier.load()
    predictions = classifier.predict(**kwargs)
    return {
        task: {
            "label": prediction.label,
            "confidence": prediction.confidence,
            "alternatives": prediction.alternatives,
        }
        for task, prediction in predictions.items()
    }


def predict_product_labels_with_linkages(**kwargs: Any) -> dict[str, Any]:
    classifier = ProductLabelClassifier.load()
    predictions = classifier.predict(**kwargs)
    labels = {
        task: {
            "label": prediction.label,
            "confidence": prediction.confidence,
            "alternatives": prediction.alternatives,
        }
        for task, prediction in predictions.items()
    }
    return {
        "label_predictions": labels,
        "candidate_chemical_linkages": classifier.candidate_chemical_linkages(predictions),
    }
