from types import SimpleNamespace

import pandas as pd

from app.services.decision_support import DecisionSupportService
from app.services.reports import ReportService


class AnalyticsStub:
    warnings = []
    sorting = SimpleNamespace(empty=True)
    production = pd.DataFrame([
        {"batch_id": "B-1", "production_timestamp": "2026-01-01T15:00:00Z",
         "production_quantity": 100, "inspected_quantity": 90,
         "accepted_quantity": 82, "rejected_quantity": 8},
    ])
    inspections = pd.DataFrame()

    def batch_summaries(self):
        return [{"batch_id": "B-1", "rejection_rate": 8.0}]

    def descriptive(self):
        return {
            "kpis": {"production_quantity": 100, "inspected_quantity": 90,
                     "accepted_quantity": 82, "rejected_quantity": 8,
                     "rejection_rate": 8.89, "inspection_coverage": 90.0},
            "warnings": [],
            "batch_summaries": [{
                "batch_id": "B-1", "production_quantity": 100,
                "inspected_quantity": 90, "accepted_quantity": 82,
                "rejected_quantity": 8, "rejection_rate": 8.89,
            }],
        }

    def trends(self, *_args):
        return [{"date": "2026-01-01", "value": 100, "production_quantity": 100,
                 "inspected_quantity": 90, "accepted_quantity": 82,
                 "rejected_quantity": 8}]


def test_decision_support_is_evidence_based_and_labels_model_source():
    service = DecisionSupportService(
        AnalyticsStub(),
        [{"batch_id": "B-2", "predicted_risk_category": "High",
          "predicted_probability": 0.91}],
    )
    recommendations = service.recommendations()
    assert {item["source"] for item in recommendations} == {"rule", "model"}
    assert any("B-1" in item["recommendation"] for item in recommendations)
    assert any("sampling" in item["recommendation"] for item in recommendations)


def test_decision_support_includes_anomaly_warning_when_available():
    class AnalyticsWithAnomaly(AnalyticsStub):
        def warnings_for_decision_support(self):
            return [{
                "code": "high_anomaly_score", "severity": "high", "batch_id": "B-1",
                "metric": "high_anomaly_score", "observed_value": 2, "threshold": 0.8,
                "recommendation": "Review anomalous inspection records.",
            }]

    recommendations = DecisionSupportService(AnalyticsWithAnomaly(), []).recommendations()
    assert recommendations[-1]["triggering_metric"] == "high_anomaly_score"


def test_report_calculation_and_exports():
    report = ReportService(AnalyticsStub(), []).build(
        "daily-production", "2026-01-01", "2026-01-02")
    assert report["metrics"]["rejected_quantity"] == 8
    assert report["rows"][0]["value"] == 100
    assert ReportService.csv_bytes(report).startswith(b"\xef\xbb\xbfReport")
    assert ReportService.pdf_bytes(report).startswith(b"%PDF")


def test_report_batch_and_date_filters_share_the_same_scope():
    report = ReportService(AnalyticsStub(), []).build(
        "batch-quality", "2026-01-01", "2026-01-01", "B-1")
    assert report["metrics"]["production_quantity"] == 100
    assert report["rows"][0]["batch_id"] == "B-1"
    outside = ReportService(AnalyticsStub(), []).build(
        "batch-quality", "2026-01-02", "2026-01-02", "B-1")
    assert outside["metrics"]["production_quantity"] is None
    assert outside["rows"] == []
