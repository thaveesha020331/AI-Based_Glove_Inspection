from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.analytics import AnalyticsService


def row(**values):
    return SimpleNamespace(**values)


def test_descriptive_metrics_use_safe_denominators():
    service = AnalyticsService(
        [row(id=1, batch_id="B1", production_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
             production_quantity=100, inspected_quantity=80, accepted_quantity=72, rejected_quantity=8)],
        [row(record_id="I1", batch_id="B1", inspection_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
             defect_category="Pinhole", defect_status="Detected"),
         row(record_id="I2", batch_id="B1", inspection_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
             defect_category="Pinhole", defect_status="Detected")],
        [row(id=1, batch_id="B1", quality_grade="A", glove_size="M", colour="Blue")],
        [],
    )
    result = service.descriptive()
    assert result["kpis"]["inspection_coverage"] == 80.0
    assert result["kpis"]["rejection_rate"] == 10.0
    assert result["defects"]["rate"] == 2.5
    assert result["quality"]["grade_distribution"] == {"A": 1, "B": 0, "C": 0, "Reject": 0}


def test_empty_and_zero_denominators_are_unavailable():
    result = AnalyticsService([], [], [], []).descriptive()
    assert result["kpis"]["rejection_rate"] is None
    assert result["kpis"]["inspection_coverage"] is None
    assert result["sorting"]["success_rate"] is None


def test_duplicate_and_inconsistent_rows_are_reported_and_excluded():
    values = dict(batch_id="B1", production_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                  production_quantity=10, inspected_quantity=11, accepted_quantity=0, rejected_quantity=0)
    service = AnalyticsService([row(id=1, **values), row(id=2, **values)], [], [], [])
    result = service.descriptive()
    codes = {warning["code"] for warning in result["warnings"]}
    assert "duplicate_records" in codes
    assert "inconsistent_quantities" in codes
    assert result["kpis"]["production_quantity"] == 0


def test_trends_and_comparison_report_missing_previous_period():
    service = AnalyticsService(
        [row(id=1, batch_id="B1", production_timestamp=datetime(2026, 1, 5, tzinfo=timezone.utc),
             production_quantity=20, inspected_quantity=20, accepted_quantity=19, rejected_quantity=1)],
        [], [], [],
    )
    assert service.trends("weekly")[0]["value"] == 20
    comparison = service.compare_period("daily", "2026-01-05", "2026-01-05")
    assert comparison["status"] == "unavailable"


def test_descriptive_exposes_anomaly_signals_from_inspection_scores():
    result = AnalyticsService(
        [], [row(record_id="I1", batch_id="B1",
                  inspection_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                  defect_category="Pinhole", defect_status="Detected",
                  anomaly_score=0.91, confidence=0.42)], [], [],
    ).descriptive()
    assert {signal["code"] for signal in result["anomalies"]} == {
        "high_anomaly_score", "low_inspection_confidence",
    }
