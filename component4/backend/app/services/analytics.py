"""Data preparation and descriptive analytics for GloveIQ.

Defect events remain separate from glove quantities: one glove may produce more
than one defect record. Defect rates therefore use inspected quantity as their
denominator and are not presented as rejected-glove rates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd
import json

PRODUCTION_COLUMNS = ("id", "batch_id", "production_timestamp", "production_quantity",
                      "inspected_quantity", "accepted_quantity", "rejected_quantity")
INSPECTION_COLUMNS = ("record_id", "batch_id", "inspection_timestamp", "defect_category", "defect_status",
                      "anomaly_score", "confidence")
QUALITY_COLUMNS = ("id", "batch_id", "glove_size", "colour", "orientation",
                   "length_measurement", "quality_grade", "batch_consistency_status",
                   "metadata_json")
SORTING_COLUMNS = ("id", "batch_id", "sorting_timestamp", "status",
                   "intended_sorting_category", "actual_sorting_outcome")
GRADES = ("A", "B", "C", "Reject")


@dataclass(frozen=True)
class AnalyticsThresholds:
    rejection_rate: float = 5.0
    sorting_failure_rate: float = 5.0
    defect_increase_percent: float = 25.0
    consistency_warning_count: int = 1


def _records(rows: Iterable[Any], fields: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        [{field: json.dumps(getattr(row, field, None), sort_keys=True)
          if isinstance(getattr(row, field, None), dict) else getattr(row, field, None)
          for field in fields} for row in rows],
        columns=list(fields),
    )


def _number(value: Any) -> int | float:
    if value is None or pd.isna(value):
        return 0
    numeric = float(value)
    return int(numeric) if numeric.is_integer() else numeric


def _pct(numerator: float, denominator: float) -> float | None:
    if denominator <= 0 or pd.isna(denominator):
        return None
    return round(float(numerator) / float(denominator) * 100, 2)


class DataPreparationService:
    """Normalize records and report issues without fabricating source values."""

    def prepare(self, rows: Iterable[Any], fields: tuple[str, ...], *,
                timestamp_field: str | None = None,
                categorical_fields: tuple[str, ...] = (),
                numeric_fields: tuple[str, ...] = ()) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
        frame = _records(rows, fields)
        warnings: list[dict[str, Any]] = []
        if frame.empty:
            return frame, warnings
        if timestamp_field:
            parsed = pd.to_datetime(frame[timestamp_field], errors="coerce", utc=True)
            if int(parsed.isna().sum()):
                warnings.append({"code": "invalid_timestamp", "field": timestamp_field,
                                 "count": int(parsed.isna().sum()),
                                 "message": "Invalid timestamps are excluded from time-series analysis."})
            frame[timestamp_field] = parsed
        for field in categorical_fields:
            missing = frame[field].isna() | frame[field].astype("string").str.strip().eq("")
            if int(missing.sum()):
                warnings.append({"code": "missing_category", "field": field,
                                 "count": int(missing.sum()),
                                 "message": f"{field} is missing and excluded from grouped summaries."})
            frame[field] = frame[field].astype("string").str.strip().replace({"": pd.NA})
        for field in numeric_fields:
            numeric = pd.to_numeric(frame[field], errors="coerce")
            missing = int(numeric.isna().sum())
            if missing:
                warnings.append({"code": "missing_numeric", "field": field, "count": missing,
                                 "message": f"{field} is missing or invalid and excluded from affected calculations."})
            frame[field] = numeric
        duplicate_subset = [field for field in fields if field != "id"]
        duplicate_mask = frame.duplicated(subset=duplicate_subset, keep="first")
        if int(duplicate_mask.sum()):
            warnings.append({"code": "duplicate_records", "count": int(duplicate_mask.sum()),
                             "message": "Duplicate records are excluded from aggregate metrics."})
            frame = frame.loc[~duplicate_mask].copy()
        return frame, warnings

    def production(self, rows: Iterable[Any]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
        frame, warnings = self.prepare(
            rows, PRODUCTION_COLUMNS, timestamp_field="production_timestamp",
            categorical_fields=("batch_id",),
            numeric_fields=("production_quantity", "inspected_quantity",
                            "accepted_quantity", "rejected_quantity"),
        )
        if frame.empty:
            return frame, warnings
        invalid = (
            (frame["production_quantity"] < 0) | (frame["inspected_quantity"] < 0) |
            (frame["accepted_quantity"] < 0) | (frame["rejected_quantity"] < 0) |
            (frame["inspected_quantity"] > frame["production_quantity"]) |
            (frame["accepted_quantity"] + frame["rejected_quantity"] > frame["inspected_quantity"])
        ).fillna(False)
        if int(invalid.sum()):
            warnings.append({"code": "inconsistent_quantities", "count": int(invalid.sum()),
                             "message": "Inconsistent production quantities are excluded from quantity metrics."})
            frame = frame.loc[~invalid].copy()
        return frame, warnings

    def inspections(self, rows: Iterable[Any]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
        rows = list(rows)
        numeric_fields = tuple(
            field for field in ("anomaly_score", "confidence")
            if any(getattr(row, field, None) is not None for row in rows)
        )
        return self.prepare(
            rows, INSPECTION_COLUMNS, timestamp_field="inspection_timestamp",
            categorical_fields=("batch_id", "defect_category", "defect_status"),
            numeric_fields=numeric_fields,
        )

    def quality(self, rows: Iterable[Any]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
        return self.prepare(rows, QUALITY_COLUMNS,
                            categorical_fields=("batch_id", "quality_grade", "glove_size", "colour",
                                                 "orientation", "batch_consistency_status"),
                            numeric_fields=("length_measurement",))

    def sorting(self, rows: Iterable[Any]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
        return self.prepare(rows, SORTING_COLUMNS, timestamp_field="sorting_timestamp",
                            categorical_fields=("batch_id", "status", "intended_sorting_category",
                                                 "actual_sorting_outcome"))


class AnalyticsService:
    def __init__(self, production_rows: Iterable[Any], inspection_rows: Iterable[Any],
                 quality_rows: Iterable[Any], sorting_rows: Iterable[Any],
                 thresholds: AnalyticsThresholds | None = None):
        preparation = DataPreparationService()
        self.production, p_warnings = preparation.production(production_rows)
        self.inspections, i_warnings = preparation.inspections(inspection_rows)
        self.quality, q_warnings = preparation.quality(quality_rows)
        self.sorting, s_warnings = preparation.sorting(sorting_rows)
        self.warnings = p_warnings + i_warnings + q_warnings + s_warnings
        self.thresholds = thresholds or AnalyticsThresholds()

    def _trend_frame(self, granularity: str = "daily", start: Any = None,
                     end: Any = None) -> pd.DataFrame:
        frame = self.production.dropna(subset=["production_timestamp"]).copy()
        if start is not None:
            start_timestamp = pd.Timestamp(start)
            if start_timestamp.tzinfo is None:
                start_timestamp = start_timestamp.tz_localize("UTC")
            else:
                start_timestamp = start_timestamp.tz_convert("UTC")
            frame = frame[frame.production_timestamp >= start_timestamp]
        if end is not None:
            end_text = str(end)
            end_timestamp = pd.Timestamp(end)
            if len(end_text) == 10:
                end_timestamp = end_timestamp + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            if end_timestamp.tzinfo is None:
                end_timestamp = end_timestamp.tz_localize("UTC")
            else:
                end_timestamp = end_timestamp.tz_convert("UTC")
            frame = frame[frame.production_timestamp <= end_timestamp]
        if frame.empty:
            return pd.DataFrame(columns=["period", "production_quantity", "inspected_quantity",
                                         "accepted_quantity", "rejected_quantity", "rejection_rate",
                                         "acceptance_rate"])
        if granularity == "daily":
            frame["period"] = frame.production_timestamp.dt.floor("D")
        elif granularity == "weekly":
            frame["period"] = (frame.production_timestamp.dt.tz_localize(None)
                               .dt.to_period("W").dt.start_time.dt.tz_localize("UTC"))
        elif granularity == "monthly":
            frame["period"] = (frame.production_timestamp.dt.tz_localize(None)
                               .dt.to_period("M").dt.start_time.dt.tz_localize("UTC"))
        else:
            raise ValueError("granularity must be daily, weekly, or monthly")
        grouped = frame.groupby("period", as_index=False)[
            ["production_quantity", "inspected_quantity", "accepted_quantity", "rejected_quantity"]
        ].sum(min_count=1)
        grouped["rejection_rate"] = grouped.apply(
            lambda row: _pct(row.rejected_quantity, row.inspected_quantity), axis=1)
        grouped["acceptance_rate"] = grouped.apply(
            lambda row: _pct(row.accepted_quantity, row.inspected_quantity), axis=1)
        return grouped

    def trends(self, granularity: str = "daily", start: Any = None, end: Any = None) -> list[dict[str, Any]]:
        result = self._trend_frame(granularity, start, end)
        output = []
        for row in result.to_dict("records"):
            period = row.pop("period")
            row["period"] = period.date().isoformat()
            row["date"] = row["period"]
            row["value"] = _number(row["production_quantity"])
            output.append({key: _number(value) if isinstance(value, (int, float, np.number)) else value
                           for key, value in row.items()})
        return output

    def compare_period(self, granularity: str = "daily", start: Any = None,
                       end: Any = None) -> dict[str, Any]:
        """Compare equal-length periods, returning unavailable when no baseline exists."""
        if start is None or end is None:
            return {"status": "unavailable", "reason": "start_date and end_date are required"}
        current_start = pd.Timestamp(start)
        current_end = pd.Timestamp(end)
        duration = current_end - current_start
        previous_start = current_start - duration - pd.Timedelta(days=1)
        previous_end = current_start - pd.Timedelta(days=1)
        current = self._trend_frame(granularity, current_start, current_end)
        previous = self._trend_frame(granularity, previous_start, previous_end)
        if previous.empty:
            return {"status": "unavailable", "reason": "No records exist in the comparable previous period"}
        current_totals = current[["production_quantity", "inspected_quantity", "rejected_quantity"]].sum()
        previous_totals = previous[["production_quantity", "inspected_quantity", "rejected_quantity"]].sum()
        return {
            "status": "available",
            "current": {"start_date": current_start.date().isoformat(),
                        "end_date": current_end.date().isoformat(),
                        "rejection_rate": _pct(current_totals.rejected_quantity,
                                               current_totals.inspected_quantity)},
            "previous": {"start_date": previous_start.date().isoformat(),
                         "end_date": previous_end.date().isoformat(),
                         "rejection_rate": _pct(previous_totals.rejected_quantity,
                                                previous_totals.inspected_quantity)},
            "change_percentage_points": round(
                (_pct(current_totals.rejected_quantity, current_totals.inspected_quantity) or 0)
                - (_pct(previous_totals.rejected_quantity, previous_totals.inspected_quantity) or 0), 2),
        }

    def descriptive(self) -> dict[str, Any]:
        p, q, quality, sorting = self.production, self.inspections, self.quality, self.sorting
        totals = {field: _number(p[field].sum()) if not p.empty else 0
                  for field in ("production_quantity", "inspected_quantity",
                                "accepted_quantity", "rejected_quantity")}
        inspected = totals["inspected_quantity"]
        defect_counts = (q.dropna(subset=["defect_category"]).groupby("defect_category")
                         .size().sort_values(ascending=False).to_dict() if not q.empty else {})
        grade_counts = {grade: int((quality.quality_grade == grade).sum()) if not quality.empty else 0
                        for grade in GRADES}
        sorting_total = len(sorting)
        sorting_success = int((sorting.status.str.casefold() == "success").sum()) if sorting_total else 0
        anomaly_signals = []
        if not q.empty:
            high_anomaly = q[q["anomaly_score"].ge(0.8)] if "anomaly_score" in q else q.iloc[0:0]
            low_confidence = q[q["confidence"].lt(0.5)] if "confidence" in q else q.iloc[0:0]
            if len(high_anomaly):
                anomaly_signals.append({
                    "code": "high_anomaly_score", "severity": "high",
                    "count": int(len(high_anomaly)), "threshold": 0.8,
                    "message": "Inspection records exceed the configured anomaly-score threshold.",
                })
            if len(low_confidence):
                anomaly_signals.append({
                    "code": "low_inspection_confidence", "severity": "medium",
                    "count": int(len(low_confidence)), "threshold": 0.5,
                    "message": "Inspection records have confidence below the configured review threshold.",
                })
        anomaly_signals.extend({
            "code": warning["code"], "severity": warning.get("severity", "medium"),
            "count": warning.get("observed_value"), "threshold": warning.get("threshold"),
            "message": warning.get("recommendation", warning.get("message", warning["code"])),
        } for warning in self.warnings if warning["code"] in {"inconsistent_quantities", "duplicate_records"})
        return {
            "kpis": {**totals,
                     "inspection_coverage": _pct(inspected, totals["production_quantity"]),
                     "rejection_rate": _pct(totals["rejected_quantity"], inspected),
                     "acceptance_rate": _pct(totals["accepted_quantity"], inspected)},
            "defects": {
                "frequency_by_category": [{"defect_category": str(key), "count": int(value)}
                                          for key, value in defect_counts.items()],
                "defect_event_count": int(sum(defect_counts.values())),
                "rate": _pct(sum(defect_counts.values()), inspected),
                "denominator": "total inspected quantity; defect records are events and are not assumed to be unique gloves",
            },
            "quality": {"grade_distribution": grade_counts,
                        "total_records": int(sum(grade_counts.values())),
                        "grade_percentages": {grade: _pct(count, sum(grade_counts.values()))
                                              for grade, count in grade_counts.items()},
                        "by_size": self._distribution("glove_size"),
                        "by_colour": self._distribution("colour")},
            "sorting": {"total": sorting_total, "success_count": sorting_success,
                        "failure_count": sorting_total - sorting_success,
                        "success_rate": _pct(sorting_success, sorting_total),
                        "by_outcome": self._distribution("actual_sorting_outcome")},
            "batch_summaries": self.batch_summaries(),
            "anomalies": anomaly_signals,
            "warnings": self.warnings,
        }

    def batch_summaries(self) -> list[dict[str, Any]]:
        if self.production.empty:
            return []
        grouped = self.production.groupby("batch_id", dropna=True)[
            ["production_quantity", "inspected_quantity", "accepted_quantity", "rejected_quantity"]
        ].sum()
        results = []
        for batch_id, row in grouped.iterrows():
            results.append({
                "batch_id": str(batch_id),
                **{key: _number(row[key]) for key in row.index},
                "rejection_rate": _pct(row.rejected_quantity, row.inspected_quantity),
                "quality_grade_counts": {
                    grade: int(((self.quality.batch_id == batch_id) &
                                (self.quality.quality_grade == grade)).sum())
                    if not self.quality.empty else 0 for grade in GRADES
                },
            })
        return results

    def _distribution(self, field: str) -> list[dict[str, Any]]:
        frame = self.quality if field in self.quality else self.sorting
        if frame.empty:
            return []
        return [{"value": str(key), "count": int(value)}
                for key, value in frame[field].dropna().value_counts().items()]

    def warnings_for_decision_support(self) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        for batch in self.batch_summaries():
            rate = batch["rejection_rate"]
            if rate is not None and rate > self.thresholds.rejection_rate:
                warnings.append(self._warning("elevated_rejection_rate", "high", batch["batch_id"],
                                              "rejection_rate", rate, self.thresholds.rejection_rate,
                                              "Review the batch and dominant defect categories before release."))
        if not self.sorting.empty:
            for batch_id, group in self.sorting.groupby("batch_id"):
                rate = _pct(int((group.status.str.casefold() == "failure").sum()), len(group))
                if rate is not None and rate > self.thresholds.sorting_failure_rate:
                    warnings.append(self._warning("sorting_failure_rate", "medium", str(batch_id),
                                                  "sorting_failure_rate", rate,
                                                  self.thresholds.sorting_failure_rate,
                                                  "Check sorter calibration and quarantine affected output."))
        if not self.inspections.empty:
            dated = self.inspections.dropna(subset=["inspection_timestamp"])
            if not dated.empty:
                periods = dated.inspection_timestamp.dt.floor("D").drop_duplicates().sort_values()
                if len(periods) >= 2:
                    latest, previous = periods.iloc[-1], periods.iloc[-2]
                    latest_count = int((dated.inspection_timestamp.dt.floor("D") == latest).sum())
                    previous_count = int((dated.inspection_timestamp.dt.floor("D") == previous).sum())
                    increase = ((latest_count - previous_count) / previous_count * 100
                                if previous_count else None)
                    if increase is not None and increase > self.thresholds.defect_increase_percent:
                        warnings.append(self._warning(
                            "defect_increase", "high", None, "defect_event_increase_percent",
                            round(increase, 2), self.thresholds.defect_increase_percent,
                            "Investigate the latest inspection period and compare defect categories with the prior period."))
            if "anomaly_score" in self.inspections:
                high_anomaly = self.inspections[self.inspections.anomaly_score.ge(0.8)]
                if len(high_anomaly):
                    warnings.append(self._warning(
                        "high_anomaly_score", "high", None, "high_anomaly_score",
                        len(high_anomaly), 0.8,
                        "Review high-anomaly inspection records and quarantine affected output until confirmed."))
            if "confidence" in self.inspections:
                low_confidence = self.inspections[self.inspections.confidence.lt(0.5)]
                if len(low_confidence):
                    warnings.append(self._warning(
                        "low_inspection_confidence", "medium", None, "low_inspection_confidence",
                        len(low_confidence), 0.5,
                        "Review low-confidence inspection records before using them for release decisions."))
        if not self.quality.empty and "batch_consistency_status" in self.quality:
            inconsistent = self.quality[
                self.quality.batch_consistency_status.fillna("").str.casefold().isin(
                    {"inconsistent", "conflict", "failed"})
            ]
            if len(inconsistent) >= self.thresholds.consistency_warning_count:
                warnings.append(self._warning(
                    "batch_inconsistency", "medium", None, "inconsistent_batch_records",
                    len(inconsistent), self.thresholds.consistency_warning_count,
                    "Reconcile repeated batch consistency failures with the production manifest."))
        return warnings

    @staticmethod
    def _warning(code: str, severity: str, batch_id: str | None, metric: str,
                 observed: Any, threshold: Any, recommendation: str) -> dict[str, Any]:
        return {"code": code, "severity": severity, "batch_id": batch_id, "metric": metric,
                "observed_value": _number(observed), "threshold": _number(threshold),
                "recommendation": recommendation}
