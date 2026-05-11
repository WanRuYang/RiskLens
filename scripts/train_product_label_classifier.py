from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LABEL_DIR = PROJECT_ROOT / "data" / "derived" / "label_datasets"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "models" / "product_label_classifier"


@dataclass(frozen=True)
class TaskSpec:
    name: str
    input_file: str
    label_column: str
    feature_columns: tuple[str, ...]
    confidence_column: str | None = None
    min_confidence: float = 0.0
    exclude_labels: tuple[str, ...] = ("unknown", "")
    test_size: float = 0.2


TASKS = [
    TaskSpec(
        name="product_category",
        input_file="prop65_product_weak_labels.csv",
        label_column="product_category_label",
        feature_columns=("product_text",),
    ),
    TaskSpec(
        name="exposure_pathway",
        input_file="prop65_product_weak_labels.csv",
        label_column="exposure_pathway_label",
        feature_columns=("product_text", "chemical_text"),
        confidence_column="label_confidence",
        min_confidence=0.65,
    ),
    TaskSpec(
        name="concern_family",
        input_file="prop65_product_weak_labels.csv",
        label_column="concern_family_label",
        feature_columns=("product_text", "chemical_text"),
        confidence_column="label_confidence",
        min_confidence=0.65,
    ),
    TaskSpec(
        name="risk_label",
        input_file="regulatory_source_weak_labels.csv",
        label_column="risk_label",
        feature_columns=(
            "chemical_text",
            "product_category_label",
            "product_scope",
            "source_authority",
            "jurisdiction",
            "regulatory_status",
            "hazard_basis",
        ),
        exclude_labels=("",),
        test_size=0.25,
    ),
]


def clean_text(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", errors="ignore") as handle:
        return list(csv.DictReader(handle))


def build_feature(row: dict[str, str], columns: tuple[str, ...]) -> str:
    return clean_text(" ".join(row.get(column, "") for column in columns))


def filter_rows(rows: list[dict[str, str]], spec: TaskSpec) -> list[dict[str, str]]:
    filtered: list[dict[str, str]] = []
    excluded = set(spec.exclude_labels)
    for row in rows:
        label = clean_text(row.get(spec.label_column, ""))
        if label in excluded:
            continue
        if spec.confidence_column:
            try:
                confidence = float(row.get(spec.confidence_column, "0") or 0)
            except ValueError:
                confidence = 0.0
            if confidence < spec.min_confidence:
                continue
        if not build_feature(row, spec.feature_columns):
            continue
        filtered.append(row)
    return filtered


def prune_small_classes(rows: list[dict[str, str]], label_column: str, min_count: int) -> list[dict[str, str]]:
    counts = Counter(row[label_column] for row in rows)
    return [row for row in rows if counts[row[label_column]] >= min_count]


def can_stratify(labels: list[str], test_size: float) -> bool:
    counts = Counter(labels)
    if min(counts.values()) < 2:
        return False
    expected_test = len(labels) * test_size
    return expected_test >= len(counts)


def make_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=50000,
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1200,
                    solver="lbfgs",
                ),
            ),
        ]
    )


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_confusion_matrix(path: Path, labels: list[str], y_true: list[str], y_pred: list[str]) -> None:
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["actual\\predicted", *labels])
        for label, values in zip(labels, matrix):
            writer.writerow([label, *values.tolist()])


def train_task(spec: TaskSpec, label_dir: Path, output_dir: Path, min_class_count: int) -> tuple[Pipeline, dict[str, Any]]:
    rows = filter_rows(read_rows(label_dir / spec.input_file), spec)
    rows = prune_small_classes(rows, spec.label_column, min_class_count)
    if len(rows) < 20:
        raise RuntimeError(f"Not enough rows for task {spec.name}: {len(rows)}")

    x = [build_feature(row, spec.feature_columns) for row in rows]
    y = [row[spec.label_column] for row in rows]
    stratify = y if can_stratify(y, spec.test_size) else None
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=spec.test_size,
        random_state=42,
        stratify=stratify,
    )

    model = make_pipeline()
    model.fit(x_train, y_train)
    y_pred = model.predict(x_test)

    labels = sorted(set(y))
    report = classification_report(y_test, y_pred, labels=labels, output_dict=True, zero_division=0)
    metrics = {
        "task": spec.name,
        "label_column": spec.label_column,
        "feature_columns": list(spec.feature_columns),
        "source_file": spec.input_file,
        "rows_total_after_filter": len(rows),
        "train_rows": len(x_train),
        "test_rows": len(x_test),
        "class_counts": dict(Counter(y).most_common()),
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_test, y_pred, average="macro", zero_division=0)), 4),
        "weighted_f1": round(float(f1_score(y_test, y_pred, average="weighted", zero_division=0)), 4),
        "classification_report": report,
    }

    task_dir = output_dir / spec.name
    task_dir.mkdir(parents=True, exist_ok=True)
    write_json(task_dir / "metrics.json", metrics)
    write_confusion_matrix(task_dir / "confusion_matrix.csv", labels, y_test, y_pred.tolist())
    with (task_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["feature_text", "actual", "predicted"])
        writer.writeheader()
        for feature_text, actual, predicted in zip(x_test, y_test, y_pred):
            writer.writerow({"feature_text": feature_text, "actual": actual, "predicted": predicted})

    return model, metrics


def write_manifest(path: Path, metrics: dict[str, dict[str, Any]], model_path: Path) -> None:
    lines = [
        "# Product Label Classifier",
        "",
        "This artifact is trained from weak labels derived from Prop 65 notices and regulatory evidence tables.",
        "It should be used as a candidate-label/routing model, not as regulatory truth.",
        "",
        f"- Model artifact: `{model_path}`",
        "- Model type: TF-IDF features + balanced logistic regression",
        "- Primary use: predict product category, exposure pathway, concern family, and regulatory risk label before Gemma writes the final user-facing explanation.",
        "",
        "## Evaluation",
        "",
        "| Task | Rows | Accuracy | Macro F1 | Weighted F1 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for task_name, task_metrics in metrics.items():
        lines.append(
            "| {task} | {rows} | {accuracy:.4f} | {macro_f1:.4f} | {weighted_f1:.4f} |".format(
                task=task_name,
                rows=task_metrics["rows_total_after_filter"],
                accuracy=task_metrics["accuracy"],
                macro_f1=task_metrics["macro_f1"],
                weighted_f1=task_metrics["weighted_f1"],
            )
        )
    lines.extend(
        [
            "",
            "## Caveats",
            "",
            "- These metrics are against held-out weak labels, not manually verified ground truth.",
            "- High scores mean the model learned the labeling rules consistently; they do not prove the rules are complete.",
            "- Low-confidence or `unknown` Prop 65 notice rows are excluded from most training tasks.",
            "- For food, the pathway label is especially important because concerns can come from declared ingredients, processing byproducts, raw-material contaminants, or packaging/contact materials.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train compact product-label classifiers from weak labels.")
    parser.add_argument("--label-dir", type=Path, default=DEFAULT_LABEL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-class-count", type=int, default=3)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    models: dict[str, Pipeline] = {}
    metrics: dict[str, dict[str, Any]] = {}
    for spec in TASKS:
        model, task_metrics = train_task(spec, args.label_dir, args.output_dir, args.min_class_count)
        models[spec.name] = model
        metrics[spec.name] = task_metrics
        print(
            f"{spec.name}: rows={task_metrics['rows_total_after_filter']} "
            f"accuracy={task_metrics['accuracy']:.4f} macro_f1={task_metrics['macro_f1']:.4f}"
        )

    artifact = {
        "metadata": {
            "model_type": "tfidf_logistic_regression",
            "label_source": "weak_supervision_prop65_and_regulatory_evidence",
            "tasks": list(metrics.keys()),
            "caveat": "Candidate-label model only; not regulatory truth.",
        },
        "metrics": metrics,
        "models": models,
    }
    model_path = args.output_dir / "product_label_classifier.joblib"
    joblib.dump(artifact, model_path)
    write_json(args.output_dir / "metrics_summary.json", metrics)
    write_manifest(args.output_dir / "MODEL_CARD.md", metrics, model_path)
    print(f"Saved model: {model_path}")


if __name__ == "__main__":
    main()
