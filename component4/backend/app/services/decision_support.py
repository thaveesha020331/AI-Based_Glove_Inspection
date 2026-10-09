"""Evidence-based alert and recommendation generation."""

from __future__ import annotations

from typing import Any

from app.services.analytics import AnalyticsService


class DecisionSupportService:
    """Translate measured analytics and model outputs into actionable conditions."""

    def __init__(self, analytics: AnalyticsService, predictions: list[dict[str, Any]],
                 rejection_threshold: float = 5.0, sorting_failure_threshold: float = 5.0):
        self.analytics = analytics
        self.predictions = predictions
        self.rejection_threshold = rejection_threshold
        self.sorting_failure_threshold = sorting_failure_threshold

    def recommendations(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for batch in self.analytics.batch_summaries():
            rate = batch.get("rejection_rate")
            if rate is not None and rate > self.rejection_threshold:
                items.append(self._item(
                    "rule", "high", batch["batch_id"], "rejection_rate", rate,
                    self.rejection_threshold, "Elevated rejection rate",
                    f"Review batch {batch['batch_id']} before release and inspect its dominant defect categories."))
        for batch_id, group in self.analytics.sorting.groupby("batch_id") if not self.analytics.sorting.empty else []:
            failures = int((group.status.str.casefold() == "failure").sum())
            rate = round(failures / len(group) * 100, 2) if len(group) else None
            if rate is not None and rate > self.sorting_failure_threshold:
                items.append(self._item(
                    "rule", "medium", str(batch_id), "sorting_failure_rate", rate,
                    self.sorting_failure_threshold, "Sorting failures elevated",
                    f"Check sorter calibration and quarantine failed outcomes for batch {batch_id}."))
        inspections = getattr(self.analytics, "inspections", None)
        if inspections is not None and not inspections.empty:
            defects = inspections.dropna(subset=["defect_category"])
            for category, count in defects.defect_category.value_counts().items():
                if count >= 3:
                    items.append(self._item(
                        "rule", "medium", None, "defect_event_count", int(count), 3,
                        f"Frequent defect category: {category}",
                        f"Inspect the {category} defect source and compare it with the affected production batches."))
        for prediction in self.predictions:
            risk = str(prediction.get("predicted_risk_category", "")).casefold()
            if risk in {"high", "medium"}:
                items.append(self._item(
                    "model", "high" if risk == "high" else "medium",
                    prediction.get("batch_id"), "predicted_quality_risk",
                    prediction.get("predicted_probability"), risk,
                    f"Model predicts {risk} quality risk",
                    "Increase sampling and review the batch using the model indicators before release."))
        existing_metrics = {item["triggering_metric"] for item in items}
        warning_builder = getattr(self.analytics, "warnings_for_decision_support", None)
        for warning in warning_builder() if warning_builder else []:
            if warning["code"] in {"elevated_rejection_rate", "sorting_failure_rate"}:
                continue
            metric = warning["metric"]
            if metric in existing_metrics:
                continue
            items.append(self._item(
                "rule", warning["severity"], warning.get("batch_id"), metric,
                warning["observed_value"], warning["threshold"], warning["code"].replace("_", " ").title(),
                warning["recommendation"],
            ))
            existing_metrics.add(metric)
        return items

    @staticmethod
    def _item(source: str, severity: str, batch_id: str | None, metric: str,
              observed: Any, threshold: Any, title: str, recommendation: str) -> dict[str, Any]:
        return {
            "source": source, "severity": severity, "batch_id": batch_id,
            "triggering_metric": metric, "observed_value": observed,
            "threshold_or_risk_context": str(threshold),
            "title": title, "description": f"{metric} observed value: {observed}.",
            "recommendation": recommendation,
        }
