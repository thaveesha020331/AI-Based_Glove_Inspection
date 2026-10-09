"""Database-backed report calculation and safe export rendering."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import BytesIO, StringIO
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


REPORT_TYPES = {
    "daily-production": "Daily production-quality report",
    "batch-quality": "Batch quality report",
    "defect-analysis": "Defect analysis report",
    "rejection-acceptance": "Rejection and acceptance summary",
    "historical-trend": "Historical trend report",
    "predictive-risk": "Predictive risk report",
}


class ReportService:
    def __init__(self, analytics: Any, predictions: list[dict[str, Any]]):
        self.analytics = analytics
        self.predictions = predictions

    def build(self, report_type: str, start: str | None = None,
              end: str | None = None, batch_id: str | None = None) -> dict[str, Any]:
        if report_type not in REPORT_TYPES:
            raise ValueError(f"Unsupported report_type. Use one of: {', '.join(REPORT_TYPES)}")
        descriptive = self.analytics.descriptive()
        metrics = self._scoped_metrics(descriptive, start, end, batch_id)
        if report_type == "batch-quality":
            rows = descriptive["batch_summaries"]
        elif report_type == "defect-analysis":
            rows = descriptive["defects"]["frequency_by_category"]
        elif report_type == "predictive-risk":
            rows = self.predictions
        else:
            rows = self.analytics.trends("daily", start, end)
        if batch_id:
            rows = [row for row in rows if str(row.get("batch_id")) == str(batch_id)]
        if start or end:
            rows = self._filter_rows_by_period(report_type, rows, start, end)
        return {
            "report_type": report_type, "title": REPORT_TYPES[report_type],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period": {"start_date": start, "end_date": end},
            "batch_id": batch_id, "metrics": metrics,
            "findings": self._findings({"kpis": metrics}),
            "columns": list(rows[0].keys()) if rows else [],
            "rows": rows,
            "data_quality_warnings": descriptive["warnings"],
        }

    def _filter_rows_by_period(self, report_type: str, rows: list[dict[str, Any]],
                               start: str | None, end: str | None) -> list[dict[str, Any]]:
        if report_type in {"daily-production", "historical-trend", "rejection-acceptance"}:
            return rows
        if report_type == "batch-quality":
            frame = self.analytics.production.copy()
            timestamp_field = "production_timestamp"
        elif report_type == "defect-analysis":
            frame = self.analytics.inspections.copy()
            timestamp_field = "inspection_timestamp"
        elif report_type == "predictive-risk":
            if not rows:
                return []
            timestamps = pd.to_datetime(
                [row.get("prediction_time") for row in rows], errors="coerce", utc=True
            )
            if start:
                start_timestamp = pd.Timestamp(start)
                if start_timestamp.tzinfo is None:
                    start_timestamp = start_timestamp.tz_localize("UTC")
                else:
                    start_timestamp = start_timestamp.tz_convert("UTC")
                timestamps = timestamps.where(timestamps >= start_timestamp)
            if end:
                end_timestamp = pd.Timestamp(end)
                if len(str(end)) == 10:
                    end_timestamp = end_timestamp + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
                if end_timestamp.tzinfo is None:
                    end_timestamp = end_timestamp.tz_localize("UTC")
                else:
                    end_timestamp = end_timestamp.tz_convert("UTC")
                timestamps = timestamps.where(timestamps <= end_timestamp)
            return [row for row, timestamp in zip(rows, timestamps) if pd.notna(timestamp)]
        else:
            frame = None
            timestamp_field = ""
        if frame is None or frame.empty:
            return []
        timestamps = pd.to_datetime(frame[timestamp_field], errors="coerce", utc=True)
        if start:
            start_timestamp = pd.Timestamp(start)
            if start_timestamp.tzinfo is None:
                start_timestamp = start_timestamp.tz_localize("UTC")
            else:
                start_timestamp = start_timestamp.tz_convert("UTC")
            timestamps = timestamps.where(timestamps >= start_timestamp)
        if end:
            end_timestamp = pd.Timestamp(end)
            if len(str(end)) == 10:
                end_timestamp = end_timestamp + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
            if end_timestamp.tzinfo is None:
                end_timestamp = end_timestamp.tz_localize("UTC")
            else:
                end_timestamp = end_timestamp.tz_convert("UTC")
            timestamps = timestamps.where(timestamps <= end_timestamp)
        if report_type == "defect-analysis":
            frame = frame.loc[timestamps.notna()].dropna(subset=["defect_category"])
            counts = frame["defect_category"].value_counts()
            return [{"defect_category": str(category), "count": int(count)}
                    for category, count in counts.items()]
        valid_batches = set(frame.loc[timestamps.notna(), "batch_id"].astype(str))
        return [row for row in rows if str(row.get("batch_id")) in valid_batches]

    def _scoped_metrics(self, descriptive: dict[str, Any], start: str | None,
                        end: str | None, batch_id: str | None) -> dict[str, Any]:
        if batch_id or start or end:
            frame = self.analytics.production.copy()
            if frame.empty:
                return {key: None for key in descriptive["kpis"]}
            timestamps = pd.to_datetime(frame["production_timestamp"], errors="coerce", utc=True)
            valid = timestamps.notna()
            if batch_id:
                valid &= frame["batch_id"].astype(str).eq(str(batch_id))
            if start:
                valid &= timestamps >= self._boundary(start)
            if end:
                valid &= timestamps <= self._boundary(end, end_of_day=True)
            frame = frame.loc[valid]
            if frame.empty:
                return {key: None for key in descriptive["kpis"]}
            totals = {key: float(frame[key].sum())
                      for key in ("production_quantity", "inspected_quantity",
                                  "accepted_quantity", "rejected_quantity")}
            totals = {key: int(value) if value.is_integer() else value for key, value in totals.items()}
            production, inspected = totals["production_quantity"], totals["inspected_quantity"]
            return {**totals,
                    "inspection_coverage": round(inspected / production * 100, 2) if production else None,
                    "rejection_rate": round(totals["rejected_quantity"] / inspected * 100, 2) if inspected else None,
                    "acceptance_rate": round(totals["accepted_quantity"] / inspected * 100, 2)
                    if inspected else None}
        return descriptive["kpis"]

    @staticmethod
    def _boundary(value: str, end_of_day: bool = False) -> pd.Timestamp:
        timestamp = pd.Timestamp(value)
        if end_of_day and len(str(value)) == 10:
            timestamp += pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        if timestamp.tzinfo is None:
            return timestamp.tz_localize("UTC")
        return timestamp.tz_convert("UTC")

    @staticmethod
    def _findings(data: dict[str, Any]) -> list[str]:
        kpis = data["kpis"]
        findings = []
        if kpis.get("rejection_rate") is not None:
            findings.append(f"Rejection rate was {kpis['rejection_rate']}% of inspected quantity.")
        if kpis.get("inspection_coverage") is not None:
            findings.append(f"Inspection coverage was {kpis['inspection_coverage']}% of production quantity.")
        if not findings:
            findings.append("No valid quantity denominator was available for rate findings.")
        return findings

    @staticmethod
    def csv_bytes(report: dict[str, Any]) -> bytes:
        stream = StringIO()
        writer = csv.writer(stream)
        writer.writerow(["Report", report["title"]])
        writer.writerow(["Generated at", report["generated_at"]])
        writer.writerow(["Start date", report["period"]["start_date"] or "All available"])
        writer.writerow(["End date", report["period"]["end_date"] or "All available"])
        writer.writerow([])
        writer.writerow(["Metric", "Value"])
        for key, value in report["metrics"].items():
            writer.writerow([key, value])
        writer.writerow([])
        if report["columns"]:
            writer.writerow(report["columns"])
            for row in report["rows"]:
                writer.writerow([row.get(column) for column in report["columns"]])
        return stream.getvalue().encode("utf-8-sig")

    @staticmethod
    def pdf_bytes(report: dict[str, Any]) -> bytes:
        output = BytesIO()
        document = SimpleDocTemplate(output, pagesize=A4, rightMargin=15 * mm,
                                     leftMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
        styles = getSampleStyleSheet()
        story = [Paragraph(report["title"], styles["Title"]),
                 Paragraph(f"Generated: {report['generated_at']}", styles["Normal"]),
                 Paragraph(f"Period: {report['period']['start_date'] or 'All available'} to {report['period']['end_date'] or 'All available'}", styles["Normal"]),
                 Spacer(1, 8)]
        metrics = [["Metric", "Value"]] + [[str(key), str(value)] for key, value in report["metrics"].items()]
        story.append(Table(metrics, style=[("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d6b8f")),
                                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                           ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
        story.append(Spacer(1, 8))
        story.append(Paragraph("Findings", styles["Heading2"]))
        for finding in report["findings"]:
            story.append(Paragraph(f"• {finding}", styles["Normal"]))
        if report["columns"]:
            story.append(Spacer(1, 8))
            table_rows = [report["columns"]] + [[str(row.get(column, "")) for column in report["columns"]] for row in report["rows"][:30]]
            story.append(Table(table_rows, repeatRows=1, style=[("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf5f8")),
                                                                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                                                                ("FONTSIZE", (0, 0), (-1, -1), 7)]))
        document.build(story)
        return output.getvalue()
