from types import SimpleNamespace

from app.services.decision_support import DecisionSupportService
from app.services.reports import ReportService


class AnalyticsStub:
    warnings = []
    sorting = SimpleNamespace(empty=True)

    def batch_summaries(self):
        return [{"batch_id": "B-1", "rejection_rate": 8.0}]

    def descriptive(self):
        return {
            "kpis": {"production_quantity": 100, "inspected_quantity": 90,
                     "accepted_quantity": 82, "rejected_quantity": 8,
                     "rejection_rate": 8.89, "inspection_coverage": 90.0},
            "warnings": [],
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


def test_report_calculation_and_exports():
    report = ReportService(AnalyticsStub(), []).build(
        "daily-production", "2026-01-01", "2026-01-02")
    assert report["metrics"]["rejected_quantity"] == 8
    assert report["rows"][0]["value"] == 100
    assert ReportService.csv_bytes(report).startswith(b"\xef\xbb\xbfReport")
    assert ReportService.pdf_bytes(report).startswith(b"%PDF")
