from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd

from app.services.predictive_risk import (
    FEATURES,
    PredictiveRiskService,
    RiskConfig,
    build_batch_frame,
)


def record(**values):
    return SimpleNamespace(**values)


def source_rows(count=12):
    production, batches, inspections, quality, sorting = [], [], [], [], []
    for index in range(count):
        batch_id = f"B-{index:02d}"
        timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=index)
        high_risk = index % 2 == 1
        production.append(record(
            batch_id=batch_id, production_timestamp=timestamp,
            production_quantity=100, inspected_quantity=100,
            rejected_quantity=10 if high_risk else 1,
        ))
        batches.append(record(batch_id=batch_id, production_line="Line A" if index % 2 else "Line B"))
        inspections.extend(record(batch_id=batch_id, defect_category="Pinhole") for _ in range(3 if high_risk else 1))
        quality.append(record(batch_id=batch_id, glove_size="M", colour="Blue",
                              quality_grade="Reject" if high_risk else "A"))
        sorting.append(record(batch_id=batch_id, status="Failure" if high_risk else "Success"))
    return production, batches, inspections, quality, sorting


def test_feature_frame_excludes_target_fields_and_creates_batch_target():
    rows = source_rows(2)
    frame = build_batch_frame(*rows)
    assert set(FEATURES).issubset(frame.columns)
    assert "rejected_quantity" not in FEATURES
    assert "quality_grade" not in FEATURES
    assert frame["target"].tolist() == [False, True]


def test_training_persists_metadata_and_evaluates_against_baseline(tmp_path):
    rows = source_rows()
    frame = build_batch_frame(*rows)
    service = PredictiveRiskService(tmp_path, RiskConfig(min_training_records=8, n_estimators=20))
    result = service.train(frame)
    assert result["state"] == "ready"
    assert result["evaluation"]["model"]["sample_size"] == 3
    assert "accuracy" in result["evaluation"]["rule_baseline"]
    assert service.status()["trained"] is True


def test_insufficient_data_and_missing_artifact_are_explicit(tmp_path):
    rows = source_rows(2)
    frame = build_batch_frame(*rows)
    service = PredictiveRiskService(tmp_path, RiskConfig(min_training_records=8))
    result = service.train(frame)
    assert result["state"] == "insufficient_data"
    assert service.predict("B-00", frame)["state"] == "unavailable"


def test_prediction_returns_probability_indicators_and_action(tmp_path):
    rows = source_rows()
    frame = build_batch_frame(*rows)
    service = PredictiveRiskService(tmp_path, RiskConfig(min_training_records=8, n_estimators=20))
    service.train(frame)
    result = service.predict("B-11", frame)
    assert result["state"] == "ready"
    assert result["risk_category"] in {"Low", "Medium", "High"}
    assert 0 <= result["risk_probability"] <= 1
    assert result["contributing_features"]
    assert result["recommended_action"]


def test_evaluation_handles_single_class_predictions_without_undefined_metrics():
    from app.services.predictive_risk import _classification_metrics

    result = _classification_metrics(pd.Series([False, True]), [False, False])
    assert result["precision"] == 0
    assert result["recall"] == 0
    assert result["roc_auc"] is None
