"""Leakage-safe batch quality-risk modelling.

The supplied CSV is synthetic demonstration data.  Only production-time
features are used by the model; inspection outcomes and quality measurements
are never model inputs.
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
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


NUMERIC_FEATURES = (
    "operator_experience_years",
    "machine_age_months",
    "temperature_c",
    "humidity_pct",
    "production_quantity",
)
CATEGORICAL_FEATURES = ("production_line", "shift")
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
RISK_LABELS = ("Low", "Medium", "High")
MODEL_FILENAME = "predictive_quality_risk.joblib"
METADATA_FILENAME = "predictive_quality_risk.json"


@dataclass(frozen=True)
class RiskConfig:
    low_probability: float = 0.33
    high_probability: float = 0.66
    random_state: int = 42
    n_estimators: int = 300
    min_training_records: int = 8


def _rows(rows: Iterable[Any], fields: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        [{field: getattr(row, field, None) for field in fields} for row in rows],
        columns=list(fields),
    )


def _metric(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 4)


def _classification_metrics(y_true: pd.Series, y_pred: np.ndarray,
                            labels: tuple[Any, ...] | None = None) -> dict[str, Any]:
    labels = labels or tuple(sorted(set(y_true) | set(y_pred)))
    matrix = confusion_matrix(y_true, y_pred, labels=list(labels))
    average = "binary" if set(labels) == {False, True} else "weighted"
    metric_kwargs = {"average": average, "zero_division": 0}
    if average == "binary":
        metric_kwargs.pop("average")
    return {
        "sample_size": int(len(y_true)),
        "accuracy": _metric(accuracy_score(y_true, y_pred)),
        "precision": _metric(precision_score(y_true, y_pred, **metric_kwargs)),
        "recall": _metric(recall_score(y_true, y_pred, **metric_kwargs)),
        "f1": _metric(f1_score(y_true, y_pred, **metric_kwargs)),
        "labels": list(labels),
        "confusion_matrix": matrix.tolist(),
        "roc_auc": None,
    }


def load_training_dataset(dataset_path: str | Path) -> pd.DataFrame:
    """Load and validate the synthetic demonstration training CSV."""
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Training dataset was not found: {path}")
    frame = pd.read_csv(path)
    required = {"batch_id", "production_date", *FEATURES, "quality_risk_label"} - {"production_quantity"}
    required.add("total_produced")
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Training dataset is missing required columns: {', '.join(missing)}")
    frame = frame.copy()
    frame["production_quantity"] = frame["total_produced"]
    frame["production_timestamp"] = pd.to_datetime(frame["production_date"], errors="coerce", utc=True)
    for field in NUMERIC_FEATURES:
        frame[field] = pd.to_numeric(frame[field], errors="coerce")
    frame["quality_risk_label"] = frame["quality_risk_label"].astype("string").str.strip()
    invalid = frame["quality_risk_label"].isna() | ~frame["quality_risk_label"].isin(RISK_LABELS)
    if invalid.any() or frame[list(FEATURES)].isna().all(axis=1).any():
        raise ValueError("Training dataset contains missing or invalid production-time values.")
    return frame[["batch_id", "production_timestamp", *FEATURES, "quality_risk_label"]].rename(
        columns={"quality_risk_label": "target"}
    )


def build_batch_frame(production_rows: Iterable[Any], batch_rows: Iterable[Any],
                      inspection_rows: Iterable[Any] = (), quality_rows: Iterable[Any] = (),
                      sorting_rows: Iterable[Any] = (), config: RiskConfig | None = None) -> pd.DataFrame:
    """Build a compatibility frame from existing records without outcome features."""
    del inspection_rows, quality_rows, sorting_rows, config
    production = _rows(production_rows, ("batch_id", "production_timestamp", "production_quantity",
                                         "inspected_quantity", "rejected_quantity"))
    batches = _rows(batch_rows, ("batch_id", "production_line"))
    if production.empty:
        return pd.DataFrame(columns=["batch_id", "production_timestamp", *FEATURES, "target"])
    production["production_timestamp"] = pd.to_datetime(production["production_timestamp"], errors="coerce", utc=True)
    for field in ("production_quantity", "inspected_quantity", "rejected_quantity"):
        production[field] = pd.to_numeric(production[field], errors="coerce")
    grouped = production.dropna(subset=["batch_id", "production_timestamp"])
    grouped = grouped[grouped["production_quantity"] > 0].groupby("batch_id", as_index=False).agg(
        production_timestamp=("production_timestamp", "min"),
        production_quantity=("production_quantity", "sum"),
        inspected_quantity=("inspected_quantity", "sum"),
        rejected_quantity=("rejected_quantity", "sum"),
    )
    grouped = grouped.merge(batches.drop_duplicates("batch_id"), on="batch_id", how="left")
    grouped["target"] = (grouped["rejected_quantity"] / grouped["inspected_quantity"] * 100 >= 5).fillna(False)
    grouped["operator_experience_years"] = np.nan
    grouped["machine_age_months"] = np.nan
    grouped["temperature_c"] = np.nan
    grouped["humidity_pct"] = np.nan
    grouped["shift"] = "Unknown"
    return grouped[["batch_id", "production_timestamp", *FEATURES, "target"]]


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
            return {"trained": True, "state": "ready",
                    **json.loads(self.metadata_path.read_text(encoding="utf-8"))}
        except (OSError, json.JSONDecodeError) as exc:
            return {"trained": False, "state": "failed",
                    "message": f"Model metadata cannot be read: {exc}"}

    def train(self, frame: pd.DataFrame) -> dict[str, Any]:
        eligible = frame.dropna(subset=["target"]).copy()
        eligible = eligible[eligible[list(FEATURES)].notna().any(axis=1)]
        if len(eligible) < max(1, self.config.min_training_records):
            return {"state": "insufficient_data", "trained": False,
                    "message": f"At least {max(1, self.config.min_training_records)} eligible batches are required.",
                    "training_record_count": int(len(eligible))}
        target = eligible["target"]
        is_legacy_binary = target.dtype == bool or set(target.unique()).issubset({True, False})
        labels = (False, True) if is_legacy_binary else RISK_LABELS
        stratify = target if target.value_counts().min() >= 2 else None
        if len(eligible) >= 20:
            train, test = train_test_split(eligible, test_size=0.25, random_state=self.config.random_state,
                                            stratify=stratify)
        else:
            split = max(1, int(len(eligible) * 0.75))
            train, test = eligible.iloc[:split], eligible.iloc[split:]
        preprocess = ColumnTransformer([
            ("numeric", Pipeline([("imputer", SimpleImputer(strategy="median"))]), list(NUMERIC_FEATURES)),
            ("categorical", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]), list(CATEGORICAL_FEATURES)),
        ])
        pipeline = Pipeline([
            ("preprocess", preprocess),
            ("classifier", RandomForestClassifier(
                n_estimators=self.config.n_estimators, random_state=self.config.random_state,
                class_weight="balanced_subsample", n_jobs=-1,
            )),
        ])
        pipeline.fit(train[list(FEATURES)], train["target"])
        training_metrics = _classification_metrics(train["target"], pipeline.predict(train[list(FEATURES)]), labels)
        evaluation_available = not test.empty and test["target"].nunique() >= 2
        evaluation = _classification_metrics(test["target"], pipeline.predict(test[list(FEATURES)]), labels) if evaluation_available else {
            "sample_size": 0,
            "message": "Holdout evaluation is unavailable because the test partition does not contain at least two classes.",
            "labels": list(labels),
        }
        evaluation["rule_baseline"] = {
            "sample_size": int(len(test)),
            "message": "No separate rule baseline is defined for production-time-only features.",
            "accuracy": None,
        }
        baseline_metrics = evaluation.pop("rule_baseline")
        version = "rf-risk-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        metadata = {
            "model_version": version,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "training_record_count": int(len(train)),
            "evaluation_record_count": int(len(test) if evaluation_available else 0),
            "feature_columns": list(FEATURES),
            "label_definition": "quality_risk_label from the synthetic demonstration dataset",
            "dataset": "glove_batch_quality_synthetic_dataset.csv (synthetic demonstration data; not factory data)",
            "evaluation": {
                "split": "stratified random 75/25 split when class counts permit it; otherwise chronological 75/25 split",
                "random_state": self.config.random_state,
                "model": evaluation,
                "rule_baseline": baseline_metrics,
                "training_metrics": training_metrics,
            },
        }
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, self.artifact_path)
        self.metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return {"state": "ready", "trained": True, **metadata}

    def predict(self, batch_id: str, frame: pd.DataFrame) -> dict[str, Any]:
        if not self.artifact_path.exists():
            return {"state": "unavailable", "message": "The model is untrained; train it before requesting predictions."}
        rows = frame[frame["batch_id"].astype(str) == str(batch_id)]
        if rows.empty:
            return {"state": "unavailable", "message": f"No eligible production-time feature data exists for batch {batch_id}."}
        try:
            pipeline = joblib.load(self.artifact_path)
            row = rows.iloc[[0]]
            probabilities = pipeline.predict_proba(row[list(FEATURES)])[0]
            classes = list(pipeline.named_steps["classifier"].classes_)
            scores = {str(label): round(float(probabilities[index]), 6) for index, label in enumerate(classes)}
            predicted = str(pipeline.predict(row[list(FEATURES)])[0])
            if set(classes) == {False, True}:
                high_probability = scores.get("True", 0.0)
                category = "High" if high_probability >= self.config.high_probability else (
                    "Medium" if high_probability >= self.config.low_probability else "Low")
                scores = {"Low": round(1 - high_probability, 6), "Medium": 0.0, "High": round(high_probability, 6)}
            else:
                category = predicted
                high_probability = scores.get("High", 0.0)
            features_used = {}
            for field in FEATURES:
                value = row.iloc[0][field]
                if pd.isna(value):
                    features_used[field] = None
                elif isinstance(value, np.generic):
                    features_used[field] = value.item()
                else:
                    features_used[field] = value
            return {
                "state": "ready", "batch_id": batch_id, "risk_category": category,
                "risk_probability": round(float(high_probability), 6),
                "probability_scores": scores,
                "model_version": self.status().get("model_version"),
                "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
                "features_used": features_used,
                "contributing_features": [{"feature": field, "importance": None} for field in FEATURES],
                "recommended_action": self._recommendation(category),
                "disclaimer": "This is a model estimate based on production-time features, not a guarantee of future defects.",
            }
        except (OSError, ValueError, KeyError) as exc:
            return {"state": "failed", "message": f"Prediction could not be generated: {exc}"}

    @staticmethod
    def _recommendation(category: str) -> str:
        return {
            "High": "Hold the batch for quality review before release.",
            "Medium": "Increase sampling and review production conditions.",
            "Low": "Continue normal monitoring and release checks.",
        }.get(category, "Collect sufficient production data before making a release decision.")
