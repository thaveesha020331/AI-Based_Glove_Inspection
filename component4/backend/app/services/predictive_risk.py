"""Batch-level predictive quality-risk modelling.

Target definition
-----------------
Each eligible batch is one training row. ``high_risk`` is true when the
historical rejected/inspected rate is at least ``rejection_threshold`` or the
share of quality records graded ``Reject`` is at least
``reject_grade_threshold``.  Rejected quantity and quality grade are target
sources only; they are deliberately absent from model features.

Features describe information available when a prediction is requested:
production quantity and coverage, observed inspection event volume/category
diversity, batch size/colour mix, and sorting workload.  Sorting status,
rejected quantity, accepted quantity, and quality grades are not features.
Rows without a valid batch id, production timestamp, positive production
quantity, or positive inspected quantity are not eligible for training.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


NUMERIC_FEATURES = (
    "production_quantity", "inspected_quantity", "inspection_coverage",
    "inspection_event_count", "defect_category_count", "quality_record_count",
    "size_category_count", "colour_category_count", "sorting_record_count",
    "sorting_failure_count", "sorting_success_rate",
)
CATEGORICAL_FEATURES = ("production_line", "dominant_size", "dominant_colour")
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
MODEL_FILENAME = "predictive_quality_risk.joblib"
METADATA_FILENAME = "predictive_quality_risk.json"


@dataclass(frozen=True)
class RiskConfig:
    rejection_threshold: float = 5.0
    reject_grade_threshold: float = 5.0
    baseline_coverage_threshold: float = 90.0
    baseline_defect_rate_threshold: float = 5.0
    low_probability: float = 0.33
    high_probability: float = 0.66
    random_state: int = 42
    n_estimators: int = 300
    min_training_records: int = 1


def _rows(rows: Iterable[Any], fields: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        [{field: getattr(row, field, None) for field in fields} for row in rows],
        columns=list(fields),
    )


def _mode(frame: pd.DataFrame, field: str) -> str | None:
    values = frame[field].dropna().astype(str).str.strip()
    return values.mode().iloc[0] if not values.empty and not values.mode().empty else None


def _metric(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 4)


def _classification_metrics(y_true: pd.Series, y_pred: np.ndarray,
                            probabilities: np.ndarray | None = None,
                            classes: np.ndarray | None = None) -> dict[str, Any]:
    matrix = confusion_matrix(y_true, y_pred, labels=[False, True])
    result: dict[str, Any] = {
        "sample_size": int(len(y_true)),
        "positive_count": int(y_true.sum()),
        "accuracy": _metric(accuracy_score(y_true, y_pred)),
        "precision": _metric(precision_score(y_true, y_pred, zero_division=0)),
        "recall": _metric(recall_score(y_true, y_pred, zero_division=0)),
        "f1": _metric(f1_score(y_true, y_pred, zero_division=0)),
        "confusion_matrix": matrix.tolist(),
    }
    if probabilities is not None and classes is not None and len(np.unique(y_true)) == 2:
        positive_index = list(classes).index(True) if True in classes else None
        if positive_index is not None:
            result["roc_auc"] = _metric(roc_auc_score(y_true, probabilities[:, positive_index]))
        else:
            result["roc_auc"] = None
    else:
        result["roc_auc"] = None
    return result


def build_batch_frame(production_rows: Iterable[Any], batch_rows: Iterable[Any],
                      inspection_rows: Iterable[Any], quality_rows: Iterable[Any],
                      sorting_rows: Iterable[Any], config: RiskConfig | None = None) -> pd.DataFrame:
    """Aggregate persisted source rows into one leakage-controlled row per batch."""
    config = config or RiskConfig()
    production = _rows(production_rows, (
        "batch_id", "production_timestamp", "production_quantity",
        "inspected_quantity", "rejected_quantity",
    ))
    batches = _rows(batch_rows, ("batch_id", "production_line"))
    inspections = _rows(inspection_rows, ("batch_id", "defect_category"))
    quality = _rows(quality_rows, ("batch_id", "glove_size", "colour", "quality_grade"))
    sorting = _rows(sorting_rows, ("batch_id", "status"))
    if production.empty:
        return pd.DataFrame(columns=["batch_id", "production_timestamp", *FEATURES,
                                     "target", "target_reason"])

    for field in ("production_quantity", "inspected_quantity", "rejected_quantity"):
        production[field] = pd.to_numeric(production[field], errors="coerce")
    production["production_timestamp"] = pd.to_datetime(
        production["production_timestamp"], errors="coerce", utc=True)
    production = production.dropna(subset=["batch_id", "production_timestamp"])
    production = production[production.production_quantity > 0]
    grouped = production.groupby("batch_id", as_index=False).agg(
        production_quantity=("production_quantity", "sum"),
        inspected_quantity=("inspected_quantity", "sum"),
        rejected_quantity=("rejected_quantity", "sum"),
        production_timestamp=("production_timestamp", "min"),
    )
    grouped["inspection_coverage"] = grouped.inspected_quantity / grouped.production_quantity * 100

    def counts(source: pd.DataFrame, field: str, prefix: str) -> pd.DataFrame:
        if source.empty:
            return pd.DataFrame(columns=["batch_id", prefix])
        source[field] = source[field].astype("string").str.strip()
        return source.groupby("batch_id")[field].agg(
            **{prefix: "count"}).reset_index()

    grouped = grouped.merge(counts(inspections, "defect_category", "inspection_event_count"),
                            on="batch_id", how="left")
    grouped["defect_category_count"] = inspections.dropna(subset=["batch_id"]).groupby(
        "batch_id")["defect_category"].nunique().reindex(grouped.batch_id).fillna(0).to_numpy() if not inspections.empty else 0
    grouped = grouped.merge(counts(quality, "glove_size", "quality_record_count"),
                            on="batch_id", how="left")
    if not quality.empty:
        size_counts = quality.groupby("batch_id")["glove_size"].nunique()
        colour_counts = quality.groupby("batch_id")["colour"].nunique()
        grouped["size_category_count"] = grouped.batch_id.map(size_counts).fillna(0)
        grouped["colour_category_count"] = grouped.batch_id.map(colour_counts).fillna(0)
        grouped["dominant_size"] = grouped.batch_id.map(
            quality.groupby("batch_id").apply(lambda frame: _mode(frame, "glove_size"),
                                              include_groups=False))
        grouped["dominant_colour"] = grouped.batch_id.map(
            quality.groupby("batch_id").apply(lambda frame: _mode(frame, "colour"),
                                              include_groups=False))
        reject_counts = quality.assign(is_reject=quality.quality_grade.astype("string").str.casefold().eq("reject")).groupby("batch_id").is_reject.mean()
        grouped["reject_grade_share"] = grouped.batch_id.map(reject_counts).fillna(0) * 100
    else:
        grouped["size_category_count"] = 0
        grouped["colour_category_count"] = 0
        grouped["dominant_size"] = None
        grouped["dominant_colour"] = None
        grouped["reject_grade_share"] = 0
    if not sorting.empty:
        sorting["status"] = sorting.status.astype("string").str.casefold()
        sort_counts = sorting.groupby("batch_id").size()
        failures = sorting.assign(is_failure=sorting.status.eq("failure")).groupby("batch_id").is_failure.sum()
        grouped["sorting_record_count"] = grouped.batch_id.map(sort_counts).fillna(0)
        grouped["sorting_failure_count"] = grouped.batch_id.map(failures).fillna(0)
    else:
        grouped["sorting_record_count"] = 0
        grouped["sorting_failure_count"] = 0
    grouped["sorting_success_rate"] = np.where(
        grouped.sorting_record_count > 0,
        (grouped.sorting_record_count - grouped.sorting_failure_count) /
        grouped.sorting_record_count * 100, np.nan)
    grouped = grouped.merge(batches.drop_duplicates("batch_id"), on="batch_id", how="left")
    grouped["target"] = (
        (grouped.rejected_quantity / grouped.inspected_quantity * 100 >= config.rejection_threshold)
        | (grouped.reject_grade_share >= config.reject_grade_threshold)
    )
    grouped["target_reason"] = np.select(
        [grouped.rejected_quantity / grouped.inspected_quantity * 100 >= config.rejection_threshold,
         grouped.reject_grade_share >= config.reject_grade_threshold],
        ["rejection_rate_threshold", "reject_grade_share_threshold"], default="below_threshold")
    return grouped[["batch_id", "production_timestamp", *FEATURES, "target", "target_reason"]]


class PredictiveRiskService:
    def __init__(self, artifact_dir: str | Path, config: RiskConfig | None = None):
        self.artifact_dir = Path(artifact_dir)
        self.config = config or RiskConfig()
        self.artifact_path = self.artifact_dir / MODEL_FILENAME
        self.metadata_path = self.artifact_dir / METADATA_FILENAME

    def status(self) -> dict[str, Any]:
        if not self.artifact_path.exists() or not self.metadata_path.exists():
            return {"trained": False, "state": "untrained",
                    "message": "No trained predictive-risk model artifact is available."}
        try:
            metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            return {"trained": True, "state": "ready", **metadata}
        except (OSError, json.JSONDecodeError) as exc:
            return {"trained": False, "state": "failed",
                    "message": f"Model metadata cannot be read: {exc}"}

    def train(self, frame: pd.DataFrame) -> dict[str, Any]:
        eligible = frame.dropna(subset=["production_timestamp", "target"]).copy()
        eligible = eligible[eligible.inspected_quantity > 0].sort_values("production_timestamp")
        if len(eligible) < max(1, self.config.min_training_records):
            return {"state": "insufficient_data", "trained": False,
                    "message": f"At least {max(1, self.config.min_training_records)} eligible batch is required.",
                    "training_record_count": int(len(eligible))}
        split = max(1, int(len(eligible) * 0.75))
        train, test = eligible.iloc[:split], eligible.iloc[split:]
        evaluation_available = (
            not test.empty
            and train.target.nunique() >= 2
            and test.target.nunique() >= 2
        )
        if not evaluation_available:
            train = eligible
            test = eligible.iloc[0:0]
        preprocess = ColumnTransformer([
            ("numeric", Pipeline([("imputer", SimpleImputer(strategy="median"))]), list(NUMERIC_FEATURES)),
            ("categorical", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]), list(CATEGORICAL_FEATURES)),
        ])
        classifier = RandomForestClassifier(
            n_estimators=self.config.n_estimators, random_state=self.config.random_state,
            class_weight="balanced_subsample", n_jobs=-1,
        )
        pipeline = Pipeline([("preprocess", preprocess), ("classifier", classifier)])
        pipeline.fit(train[list(FEATURES)], train.target.astype(bool))
        train_predicted = pipeline.predict(train[list(FEATURES)])
        train_probabilities = pipeline.predict_proba(train[list(FEATURES)])
        train_classes = pipeline.named_steps["classifier"].classes_
        training_metrics = _classification_metrics(
            train.target.astype(bool), train_predicted,
            train_probabilities, train_classes,
        )
        if evaluation_available:
            predicted = pipeline.predict(test[list(FEATURES)])
            probabilities = pipeline.predict_proba(test[list(FEATURES)])
            classes = pipeline.named_steps["classifier"].classes_
            model_metrics = _classification_metrics(test.target.astype(bool), predicted, probabilities, classes)
            baseline_pred = (
                (test.inspection_coverage < self.config.baseline_coverage_threshold)
                | ((test.inspection_event_count / test.inspected_quantity * 100)
                   >= self.config.baseline_defect_rate_threshold)
            )
            baseline_metrics = _classification_metrics(test.target.astype(bool), baseline_pred.to_numpy())
        else:
            model_metrics = {
                "sample_size": 0,
                "message": "Holdout evaluation unavailable: existing batches do not contain both target classes in a chronological holdout.",
                "training_metrics": training_metrics,
            }
            baseline_metrics = {"sample_size": 0, "message": "Evaluation unavailable: existing batches do not contain both target classes in a chronological holdout."}
        version = "rf-risk-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        metadata = {
            "model_version": version, "trained_at": datetime.now(timezone.utc).isoformat(),
            "training_record_count": int(len(train)), "evaluation_record_count": int(len(test)),
            "feature_columns": list(FEATURES),
            "label_definition": "high_risk when rejection rate or Reject-grade share meets configured threshold",
            "thresholds": {"rejection_rate": self.config.rejection_threshold,
                           "reject_grade_share": self.config.reject_grade_threshold,
                           "low_probability": self.config.low_probability,
                           "high_probability": self.config.high_probability},
            "evaluation": {"conditions": "chronological 75/25 batch split when both classes are available; otherwise full-data baseline model with no evaluation metrics",
                           "random_state": self.config.random_state,
                           "model": model_metrics, "training_metrics": training_metrics,
                           "rule_baseline": baseline_metrics},
        }
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, self.artifact_path)
        self.metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return {"state": "ready", "trained": True, **metadata}

    def predict(self, batch_id: str, frame: pd.DataFrame) -> dict[str, Any]:
        if not self.artifact_path.exists():
            return {"state": "unavailable", "message": "The model is untrained; train it before requesting predictions."}
        rows = frame[frame.batch_id.astype(str) == str(batch_id)]
        if rows.empty:
            return {"state": "unavailable", "message": f"No eligible feature data exists for batch {batch_id}."}
        try:
            pipeline = joblib.load(self.artifact_path)
            row = rows.iloc[[0]]
            probabilities = pipeline.predict_proba(row[list(FEATURES)])[0]
            classes = pipeline.named_steps["classifier"].classes_
            high_index = list(classes).index(True) if True in classes else None
            probability = float(probabilities[high_index]) if high_index is not None else 0.0
            if high_index is None and len(classes) == 1 and bool(classes[0]) is False:
                category = "Low"
            elif probability >= self.config.high_probability:
                category = "High"
            elif probability >= self.config.low_probability:
                category = "Medium"
            else:
                category = "Low"
            importances = pipeline.named_steps["classifier"].feature_importances_
            transformed_names = pipeline.named_steps["preprocess"].get_feature_names_out()
            top = sorted(zip(transformed_names, importances), key=lambda item: item[1], reverse=True)[:5]
            return {
                "state": "ready", "batch_id": batch_id, "risk_category": category,
                "risk_probability": _metric(probability),
                "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
                "model_version": self.status().get("model_version"),
                "contributing_features": [{"feature": name, "importance": _metric(value)}
                                           for name, value in top],
                "observed_indicators": {field: _metric(row.iloc[0][field]) if field in NUMERIC_FEATURES
                                        else row.iloc[0][field] for field in FEATURES
                                        if pd.notna(row.iloc[0][field])},
                "recommended_action": self._recommendation(category),
                "disclaimer": "This risk score is a model estimate, not a guarantee of future defects.",
            }
        except (OSError, ValueError, KeyError, AttributeError) as exc:
            return {"state": "failed", "message": f"Prediction failed: {exc}"}

    @staticmethod
    def _recommendation(category: str) -> str:
        return {
            "High": "Hold the batch for quality review and inspect dominant contributing indicators.",
            "Medium": "Increase sampling and review the batch before release.",
            "Low": "Continue routine inspection and monitor subsequent observations.",
        }.get(category, "Collect sufficient quality observations before making a release decision.")
