"""Versioned, database-backed API for the GloveIQ dashboard."""

import io
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Blueprint, current_app, jsonify, request, send_file
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import (
    AuditLog, Batch, InspectionRecord, PredictionRecord, ProductionRecord,
    QualityAlert, QualityRecord, ReportRecord, SortingRecord,
)
from app.models.entities import model_to_dict
from app.services.analytics import AnalyticsService, AnalyticsThresholds
from app.services.predictive_risk import PredictiveRiskService, RiskConfig, build_batch_frame
from app.services.decision_support import DecisionSupportService
from app.services.reports import ReportService

api_v1_bp = Blueprint("api_v1", __name__)

VALID_GRADES = {"A", "B", "C", "Reject"}
REQUIRED_COLUMNS = {
    "production": {"batch_id", "production_timestamp", "production_quantity"},
    "inspection": {"record_id", "batch_id", "defect_category", "defect_status", "inspection_timestamp"},
    "quality": {"batch_id", "glove_size", "colour", "length_measurement", "orientation", "quality_grade", "batch_consistency_status"},
    "sorting": {"batch_id", "intended_sorting_category", "actual_sorting_outcome", "status", "sorting_timestamp"},
}


def response(data, status=200, meta=None):
    payload = {"data": data}
    if meta is not None:
        payload["meta"] = meta
    return jsonify(payload), status


def error(message, code="validation_error", status=400, details=None):
    body = {"code": code, "message": message}
    if details:
        body["details"] = details
    return jsonify({"error": body}), status


def _safe_rate(numerator, denominator):
    return round(float(numerator) / float(denominator) * 100, 2) if denominator else None


def parse_date(value, field):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a valid ISO-8601 date/time.")


def params():
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 25, type=int), 1), 100)
    return page, per_page


def paginate(query):
    page, per_page = params()
    result = query.paginate(page=page, per_page=per_page, error_out=False)
    return result.items, {"page": page, "per_page": per_page, "total": result.total, "pages": result.pages}


def apply_common_filters(query, timestamp_column):
    batch_id = request.args.get("batch_id")
    search = request.args.get("search")
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    if batch_id:
        query = query.filter_by(batch_id=batch_id)
    if start:
        try:
            query = query.filter(timestamp_column >= parse_date(start, "start_date"))
        except ValueError as exc:
            raise exc
    if end:
        query = query.filter(timestamp_column <= parse_date(end, "end_date"))
    if search:
        query = query.filter(Batch.batch_id.ilike(f"%{search}%"))
    return query


def get_or_create_batch(batch_id, timestamp, metadata=None):
    batch = db.session.get(Batch, batch_id)
    if not batch:
        batch = Batch(batch_id=batch_id, production_date=timestamp, metadata_json=metadata or {})
        db.session.add(batch)
    return batch


def audit(action, entity_type, entity_id, details=None):
    db.session.add(AuditLog(action=action, entity_type=entity_type, entity_id=str(entity_id), details=details or {}))


def analytics_service():
    """Build analytics from the persistent source tables for this request."""
    return AnalyticsService(
        ProductionRecord.query.all(),
        InspectionRecord.query.all(),
        QualityRecord.query.all(),
        SortingRecord.query.all(),
        AnalyticsThresholds(
            rejection_rate=float(current_app.config.get("QUALITY_REJECTION_THRESHOLD", 5.0)),
            sorting_failure_rate=float(current_app.config.get("SORTING_FAILURE_THRESHOLD", 5.0)),
            defect_increase_percent=float(current_app.config.get("DEFECT_INCREASE_THRESHOLD", 25.0)),
        ),
    )


def predictive_risk_service():
    model_dir = current_app.config.get("PREDICTIVE_MODEL_DIR") or str(
        Path(current_app.root_path).parent.parent / "models"
    )
    return PredictiveRiskService(model_dir, RiskConfig(
        rejection_threshold=float(current_app.config.get("QUALITY_REJECTION_THRESHOLD", 5.0)),
        reject_grade_threshold=float(current_app.config.get("REJECT_GRADE_THRESHOLD", 5.0)),
        low_probability=float(current_app.config.get("RISK_LOW_PROBABILITY", 0.33)),
        high_probability=float(current_app.config.get("RISK_HIGH_PROBABILITY", 0.66)),
        random_state=int(current_app.config.get("PREDICTIVE_RANDOM_STATE", 42)),
        n_estimators=int(current_app.config.get("PREDICTIVE_N_ESTIMATORS", 300)),
        min_training_records=int(current_app.config.get("PREDICTIVE_MIN_RECORDS", 8)),
    ))


def predictive_frame():
    return build_batch_frame(
        ProductionRecord.query.all(), Batch.query.all(), InspectionRecord.query.all(),
        QualityRecord.query.all(), SortingRecord.query.all(),
        predictive_risk_service().config,
    )


@api_v1_bp.get("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        database = "ok"
    except Exception:
        current_app.logger.exception("Database health check failed")
        database = "error"
    return response({"status": "ok" if database == "ok" else "degraded", "service": "gloveiq-api", "database": database})


@api_v1_bp.get("/dashboard/summary")
def dashboard_summary():
    data = analytics_service().descriptive()
    data["batch_count"] = Batch.query.count()
    return response({**data["kpis"], "batch_count": data["batch_count"],
                     "data_quality_warnings": data["warnings"]})


def _trend(timestamp_column, quantity_column=None):
    query = db.session.query(func.date(timestamp_column).label("date"))
    if quantity_column is None:
        query = query.add_columns(func.count().label("value"))
    else:
        query = query.add_columns(func.sum(quantity_column).label("value"))
    rows = query.group_by(func.date(timestamp_column)).order_by(func.date(timestamp_column)).all()
    return [{"date": str(row.date), "value": int(row.value or 0)} for row in rows]


@api_v1_bp.get("/dashboard/trends")
@api_v1_bp.get("/analytics/trends")
def dashboard_trends():
    try:
        service = analytics_service()
        series = service.trends(request.args.get("granularity", "daily"),
                                request.args.get("start_date"), request.args.get("end_date"))
        if request.args.get("compare", "false").lower() == "true":
            return response({"series": series, "comparison": service.compare_period(
                request.args.get("granularity", "daily"),
                request.args.get("start_date"), request.args.get("end_date")),
                "data_quality_warnings": service.warnings})
        return response(series)
    except ValueError as exc:
        return error(str(exc))


@api_v1_bp.get("/analytics/descriptive")
def descriptive_analytics():
    """Return calculated KPIs, distributions, batch summaries and quality notes."""
    return response(analytics_service().descriptive())


@api_v1_bp.get("/analytics/decision-support")
def decision_support():
    """Return evidence-based recommendations without creating alerts."""
    service = DecisionSupportService(analytics_service(), prediction_dicts())
    return response({"warnings": service.recommendations(),
                     "data_quality_warnings": service.analytics.warnings})


def prediction_dicts():
    return [model_to_dict(row) for row in PredictionRecord.query
            .filter_by(prediction_status="Completed")
            .order_by(PredictionRecord.prediction_time.desc()).all()]


@api_v1_bp.get("/production")
def production_list():
    try:
        query = ProductionRecord.query
        if request.args.get("batch_id"):
            query = query.filter_by(batch_id=request.args["batch_id"])
        if request.args.get("start_date"):
            query = query.filter(ProductionRecord.production_timestamp >= parse_date(request.args["start_date"], "start_date"))
        if request.args.get("end_date"):
            query = query.filter(ProductionRecord.production_timestamp <= parse_date(request.args["end_date"], "end_date"))
        query = query.order_by(ProductionRecord.production_timestamp.desc())
        rows, meta = paginate(query)
        return response([model_to_dict(row) for row in rows], meta=meta)
    except ValueError as exc:
        return error(str(exc))


@api_v1_bp.post("/production")
def production_create():
    payload = request.get_json(silent=True) or {}
    try:
        required = ["batch_id", "production_timestamp", "production_quantity"]
        missing = [key for key in required if payload.get(key) is None]
        if missing:
            return error("Missing required fields.", details={"fields": missing})
        timestamp = parse_date(payload["production_timestamp"], "production_timestamp")
        quantities = {key: int(payload.get(key, 0)) for key in ("production_quantity", "inspected_quantity", "accepted_quantity", "rejected_quantity")}
        if any(value < 0 for value in quantities.values()) or quantities["inspected_quantity"] > quantities["production_quantity"] or quantities["accepted_quantity"] + quantities["rejected_quantity"] > quantities["inspected_quantity"]:
            return error("Quantities must be non-negative and internally consistent.")
        get_or_create_batch(payload["batch_id"], timestamp)
        record = ProductionRecord(batch_id=payload["batch_id"], production_timestamp=timestamp, metadata_json=payload.get("metadata", {}), **quantities)
        db.session.add(record)
        audit("create", "ProductionRecord", payload["batch_id"])
        db.session.commit()
        return response(model_to_dict(record), 201)
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return error(str(exc))
    except IntegrityError:
        db.session.rollback()
        return error("Record violates a uniqueness or database constraint.", "conflict", 409)


@api_v1_bp.get("/batches")
def batches():
    query = Batch.query.order_by(Batch.production_date.desc())
    if request.args.get("quality_grade"):
        query = query.filter(Batch.current_quality_status == request.args["quality_grade"])
    if request.args.get("search"):
        query = query.filter(Batch.batch_id.ilike(f"%{request.args['search']}%"))
    rows, meta = paginate(query)
    return response([model_to_dict(row) for row in rows], meta=meta)


@api_v1_bp.get("/batches/<string:batch_id>")
def batch_detail(batch_id):
    batch = db.session.get(Batch, batch_id)
    if not batch:
        return error("Batch not found.", "not_found", 404)
    return response(model_to_dict(batch))


@api_v1_bp.get("/batches/<string:batch_id>/quality")
def batch_quality(batch_id):
    if not db.session.get(Batch, batch_id):
        return error("Batch not found.", "not_found", 404)
    rows = QualityRecord.query.filter_by(batch_id=batch_id).order_by(QualityRecord.created_at.desc()).all()
    return response([model_to_dict(row) for row in rows])


@api_v1_bp.post("/quality")
def quality_create():
    payload = request.get_json(silent=True) or {}
    required = ["batch_id", "glove_size", "colour", "length_measurement", "orientation", "quality_grade", "batch_consistency_status"]
    missing = [key for key in required if payload.get(key) is None]
    if missing:
        return error("Missing required fields.", details={"fields": missing})
    if payload["quality_grade"] not in VALID_GRADES or payload["orientation"] not in {"Left", "Right"}:
        return error("quality_grade or orientation is invalid.")
    try:
        if not db.session.get(Batch, payload["batch_id"]):
            return error("Batch does not exist.", "not_found", 404)
        record = QualityRecord(
            batch_id=payload["batch_id"], glove_size=payload["glove_size"],
            colour=payload["colour"], length_measurement=payload["length_measurement"],
            orientation=payload["orientation"], quality_grade=payload["quality_grade"],
            batch_consistency_status=payload["batch_consistency_status"],
            metadata_json=payload.get("metadata", {}),
        )
        db.session.add(record)
        audit("create", "QualityRecord", payload["batch_id"])
        db.session.commit()
        return response(model_to_dict(record), 201)
    except (TypeError, ValueError):
        db.session.rollback()
        return error("length_measurement must be a non-negative number.")


@api_v1_bp.post("/sorting")
def sorting_create():
    payload = request.get_json(silent=True) or {}
    required = ["batch_id", "intended_sorting_category", "actual_sorting_outcome", "status"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        return error("Missing required fields.", details={"fields": missing})
    if payload["status"] not in {"Success", "Failure"}:
        return error("status must be Success or Failure.")
    try:
        if not db.session.get(Batch, payload["batch_id"]):
            return error("Batch does not exist.", "not_found", 404)
        record = SortingRecord(
            batch_id=payload["batch_id"],
            intended_sorting_category=payload["intended_sorting_category"],
            actual_sorting_outcome=payload["actual_sorting_outcome"],
            status=payload["status"],
            sorting_timestamp=parse_date(payload.get("sorting_timestamp", datetime.now(timezone.utc).isoformat()), "sorting_timestamp"),
            metadata_json=payload.get("metadata", {}),
        )
        db.session.add(record)
        audit("create", "SortingRecord", payload["batch_id"])
        db.session.commit()
        return response(model_to_dict(record), 201)
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return error(str(exc))


@api_v1_bp.get("/defects/summary")
def defects_summary():
    rows = db.session.query(InspectionRecord.defect_category, func.count(InspectionRecord.record_id)).group_by(InspectionRecord.defect_category).order_by(func.count().desc()).all()
    return response([{"defect_category": category, "count": count} for category, count in rows])


@api_v1_bp.get("/defects/trends")
def defects_trends():
    return response(_trend(InspectionRecord.inspection_timestamp))


@api_v1_bp.get("/sorting/summary")
def sorting_summary():
    rows = db.session.query(SortingRecord.status, func.count(SortingRecord.id)).group_by(SortingRecord.status).all()
    return response([{"status": status, "count": count} for status, count in rows])


@api_v1_bp.get("/analytics/quality")
def quality_analytics():
    data = analytics_service().descriptive()
    distribution = data["quality"]["grade_distribution"]
    total = data["quality"]["total_records"]
    return response({"grade_distribution": distribution, "total": total,
                     "pass_rate": _safe_rate(distribution.get("A", 0) + distribution.get("B", 0), total),
                     "data_quality_warnings": data["warnings"]})


@api_v1_bp.get("/predictions")
def predictions():
    query = PredictionRecord.query.order_by(PredictionRecord.prediction_time.desc())
    if request.args.get("risk_level"):
        query = query.filter_by(predicted_risk_category=request.args["risk_level"])
    rows, meta = paginate(query)
    return response([model_to_dict(row) for row in rows], meta=meta)


@api_v1_bp.get("/predictions/status")
def predictions_status():
    return response(predictive_risk_service().status())


@api_v1_bp.get("/predictions/analytics")
def predictions_analytics():
    query = PredictionRecord.query.order_by(PredictionRecord.prediction_time.desc())
    records = [model_to_dict(row) for row in query.all()]
    distribution = {}
    for record in records:
        category = record["predicted_risk_category"]
        distribution[category] = distribution.get(category, 0) + 1
    return response({
        "model": predictive_risk_service().status(),
        "risk_distribution": distribution,
        "history": records,
    })


@api_v1_bp.post("/predictions/train")
def predictions_train():
    service = predictive_risk_service()
    result = service.train(predictive_frame())
    return response(result, 200 if result.get("trained") else 422)


@api_v1_bp.post("/predictions/predict")
def predictions_predict():
    payload = request.get_json(silent=True) or {}
    batch_id = payload.get("batch_id")
    if not batch_id:
        return error("batch_id is required.", details={"fields": ["batch_id"]})
    if not db.session.get(Batch, batch_id):
        return error("Batch does not exist.", "not_found", 404)
    result = predictive_risk_service().predict(batch_id, predictive_frame())
    if result.get("state") != "ready":
        return response(result, 200)
    prediction = PredictionRecord(
        batch_id=batch_id,
        predicted_risk_category=result["risk_category"],
        predicted_probability=result["risk_probability"],
        model_version=result["model_version"] or "unknown",
        prediction_time=parse_date(result["prediction_timestamp"], "prediction_timestamp"),
        prediction_status="Completed",
    )
    db.session.add(prediction)
    audit("create", "PredictionRecord", batch_id, {
        "risk_category": result["risk_category"],
        "model_version": result["model_version"],
    })
    db.session.commit()
    result["prediction_id"] = prediction.id
    return response(result, 201)


@api_v1_bp.post("/predictions")
def prediction_create():
    payload = request.get_json(silent=True) or {}
    required = ["batch_id", "predicted_risk_category", "model_version"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        return error("Missing required fields.", details={"fields": missing})
    try:
        prediction = PredictionRecord(batch_id=payload["batch_id"], predicted_risk_category=payload["predicted_risk_category"],
                                      predicted_probability=payload.get("predicted_probability"), model_version=payload["model_version"],
                                      prediction_time=parse_date(payload.get("prediction_time", datetime.now(timezone.utc).isoformat()), "prediction_time"),
                                      prediction_status=payload.get("prediction_status", "Completed"))
        if not db.session.get(Batch, payload["batch_id"]):
            return error("Batch does not exist.", "not_found", 404)
        db.session.add(prediction)
        audit("create", "PredictionRecord", payload["batch_id"])
        db.session.commit()
        return response(model_to_dict(prediction), 201)
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return error(str(exc))
    except IntegrityError:
        db.session.rollback()
        return error("Prediction violates a database constraint.", "conflict", 409)


@api_v1_bp.get("/alerts")
def alerts():
    query = QualityAlert.query.order_by(QualityAlert.created_at.desc())
    for field in ("status", "severity", "batch_id"):
        if request.args.get(field):
            query = query.filter(getattr(QualityAlert, field) == request.args[field])
    if request.args.get("search"):
        term = f"%{request.args['search']}%"
        query = query.filter(or_(QualityAlert.title.ilike(term),
                                 QualityAlert.description.ilike(term),
                                 QualityAlert.triggering_metric.ilike(term)))
    if request.args.get("start_date"):
        query = query.filter(QualityAlert.created_at >= parse_date(request.args["start_date"], "start_date"))
    if request.args.get("end_date"):
        query = query.filter(QualityAlert.created_at <= parse_date(request.args["end_date"], "end_date"))
    rows, meta = paginate(query)
    data = []
    for row in rows:
        item = model_to_dict(row)
        item["source"] = "model" if row.triggering_metric == "predicted_quality_risk" else "rule"
        data.append(item)
    return response(data, meta=meta)


@api_v1_bp.get("/alerts/summary")
def alerts_summary():
    rows = QualityAlert.query.filter(QualityAlert.status.in_(("Open", "Acknowledged"))).all()
    counts = {severity: sum(alert.severity.casefold() == severity for alert in rows)
              for severity in ("critical", "high", "medium", "low")}
    return response({"active_total": len(rows), "by_severity": counts,
                     "statuses": {status: sum(alert.status == status for alert in rows)
                                  for status in ("Open", "Acknowledged")}})


@api_v1_bp.post("/alerts/generate")
def alerts_generate():
    service = DecisionSupportService(analytics_service(), prediction_dicts())
    active = {(alert.triggering_metric, alert.batch_id)
              for alert in QualityAlert.query.filter(
                  QualityAlert.status.in_(("Open", "Acknowledged"))).all()}
    created = []
    for item in service.recommendations():
        key = (item["triggering_metric"], item["batch_id"])
        if key in active:
            continue
        alert = QualityAlert(
            severity=item["severity"], title=item["title"], description=item["description"],
            batch_id=item["batch_id"], triggering_metric=item["triggering_metric"],
            observed_value=item["observed_value"],
            threshold_or_risk_context=item["threshold_or_risk_context"],
            recommendation=item["recommendation"], status="Open",
        )
        db.session.add(alert)
        created.append(alert)
        active.add(key)
    if created:
        audit("generate", "QualityAlert", None, {"created": len(created)})
        db.session.commit()
    return response({"created": len(created), "skipped_duplicates": len(service.recommendations()) - len(created)})


@api_v1_bp.patch("/alerts/<int:alert_id>")
def alert_update(alert_id):
    alert = db.session.get(QualityAlert, alert_id)
    if not alert:
        return error("Alert not found.", "not_found", 404)
    payload = request.get_json(silent=True) or {}
    if "status" not in payload or payload["status"] not in {"Open", "Acknowledged", "Resolved"}:
        return error("status must be Open, Acknowledged, or Resolved.")
    alert.status = payload["status"]
    audit("update", "QualityAlert", alert_id, {"status": alert.status})
    db.session.commit()
    return response(model_to_dict(alert))


@api_v1_bp.get("/reports")
def reports():
    query = ReportRecord.query.order_by(ReportRecord.created_at.desc())
    if request.args.get("report_type"):
        query = query.filter_by(report_type=request.args["report_type"])
    rows, meta = paginate(query)
    return response([model_to_dict(row) for row in rows], meta=meta)


def report_service():
    return ReportService(analytics_service(), prediction_dicts())


@api_v1_bp.post("/reports/preview")
def report_preview():
    payload = request.get_json(silent=True) or {}
    try:
        report = report_service().build(payload.get("report_type", ""), payload.get("start_date"),
                                        payload.get("end_date"), payload.get("batch_id"))
        return response(report)
    except ValueError as exc:
        return error(str(exc))


@api_v1_bp.post("/reports/export")
def report_export():
    payload = request.get_json(silent=True) or {}
    export_format = payload.get("format", "csv").lower()
    if export_format not in {"csv", "pdf"}:
        return error("format must be csv or pdf.")
    try:
        report = report_service().build(payload.get("report_type", ""), payload.get("start_date"),
                                        payload.get("end_date"), payload.get("batch_id"))
        record = ReportRecord(report_type=report["report_type"],
                              parameters={key: payload.get(key) for key in ("start_date", "end_date", "batch_id")},
                              status="Completed", file_reference=f"report-{report['generated_at']}")
        db.session.add(record)
        audit("export", "ReportRecord", report["report_type"], {"format": export_format})
        db.session.commit()
        if export_format == "pdf":
            return send_file(io.BytesIO(report_service().pdf_bytes(report)), mimetype="application/pdf",
                             as_attachment=True, download_name=f"{report['report_type']}.pdf")
        if export_format == "csv":
            return send_file(io.BytesIO(report_service().csv_bytes(report)), mimetype="text/csv",
                             as_attachment=True, download_name=f"{report['report_type']}.csv")
    except ValueError as exc:
        return error(str(exc))


@api_v1_bp.post("/reports")
def report_create():
    payload = request.get_json(silent=True) or {}
    if not payload.get("report_type"):
        return error("report_type is required.")
    report = ReportRecord(report_type=payload["report_type"], parameters=payload.get("parameters", {}), status="Queued")
    db.session.add(report)
    audit("create", "ReportRecord", report.report_type)
    db.session.commit()
    return response(model_to_dict(report), 201)


@api_v1_bp.get("/history")
def history():
    query = InspectionRecord.query.order_by(InspectionRecord.inspection_timestamp.desc())
    rows, meta = paginate(query)
    return response([model_to_dict(row) for row in rows], meta=meta)


@api_v1_bp.get("/data-management/summary")
def data_management_summary():
    return response({"batches": Batch.query.count(), "production_records": ProductionRecord.query.count(),
                     "inspection_records": InspectionRecord.query.count(), "quality_records": QualityRecord.query.count(),
                     "sorting_records": SortingRecord.query.count()})


def _import_row(kind, row, line_number):
    timestamp_field = {"production": "production_timestamp", "inspection": "inspection_timestamp", "sorting": "sorting_timestamp"}.get(kind)
    timestamp = parse_date(row[timestamp_field], timestamp_field) if timestamp_field else datetime.now(timezone.utc)
    batch_id = row["batch_id"]
    get_or_create_batch(batch_id, timestamp)
    if kind == "production":
        values = {field: int(row.get(field, 0) or 0) for field in ("production_quantity", "inspected_quantity", "accepted_quantity", "rejected_quantity")}
        if any(v < 0 for v in values.values()) or values["inspected_quantity"] > values["production_quantity"] or values["accepted_quantity"] + values["rejected_quantity"] > values["inspected_quantity"]:
            raise ValueError(f"line {line_number}: quantities are inconsistent")
        return ProductionRecord(batch_id=batch_id, production_timestamp=timestamp, metadata_json={"source": "csv"}, **values)
    if kind == "inspection":
        return InspectionRecord(record_id=row["record_id"], batch_id=batch_id, defect_category=row["defect_category"], defect_status=row["defect_status"], anomaly_score=row.get("anomaly_score") or None, confidence=row.get("confidence") or None, inspection_timestamp=timestamp, metadata_json={"source": "csv"})
    if kind == "quality":
        if row["quality_grade"] not in VALID_GRADES or row["orientation"] not in {"Left", "Right"}:
            raise ValueError(f"line {line_number}: invalid quality grade or orientation")
        return QualityRecord(batch_id=batch_id, glove_size=row["glove_size"], colour=row["colour"], length_measurement=row["length_measurement"], orientation=row["orientation"], quality_grade=row["quality_grade"], batch_consistency_status=row["batch_consistency_status"], metadata_json={"source": "csv"})
    return SortingRecord(batch_id=batch_id, intended_sorting_category=row["intended_sorting_category"], actual_sorting_outcome=row["actual_sorting_outcome"], status=row["status"], sorting_timestamp=timestamp, metadata_json={"source": "csv"})


@api_v1_bp.post("/data-management/import")
def import_csv():
    upload = request.files.get("file")
    kind = request.form.get("record_type", "production")
    preview = request.form.get("preview", "false").lower() == "true"
    if not upload or not upload.filename.lower().endswith(".csv"):
        return error("A CSV file is required.")
    if kind not in REQUIRED_COLUMNS:
        return error("record_type is not supported.")
    try:
        content = upload.stream.read(current_app.config["MAX_CONTENT_LENGTH"] + 1)
        if len(content) > current_app.config["MAX_CONTENT_LENGTH"]:
            return error("Upload exceeds the configured size limit.", "payload_too_large", 413)
        frame = pd.read_csv(io.BytesIO(content), dtype=str).replace({np.nan: None})
        missing = sorted(REQUIRED_COLUMNS[kind] - set(frame.columns))
        if missing:
            return error("CSV is missing required columns.", details={"columns": missing})
        data_quality_warnings = []
        optional_quantity_fields = {"inspected_quantity", "accepted_quantity", "rejected_quantity"}
        absent_quantities = sorted(optional_quantity_fields - set(frame.columns)) if kind == "production" else []
        if absent_quantities:
            data_quality_warnings.append({
                "code": "missing_production_values", "fields": absent_quantities,
                "message": "Missing quantity fields use the database schema default of zero; verify before using coverage or rate KPIs.",
            })
        if preview:
            return response({"columns": list(frame.columns), "rows": frame.head(10).to_dict(orient="records"),
                             "row_count": len(frame), "data_quality_warnings": data_quality_warnings})
        records = [_import_row(kind, row, index + 2) for index, row in enumerate(frame.to_dict(orient="records"))]
        db.session.add_all(records)
        audit("import", kind, None, {"rows": len(records), "filename": upload.filename})
        db.session.commit()
        return response({"imported": len(records), "record_type": kind,
                         "data_quality_warnings": data_quality_warnings}, 201)
    except (ValueError, TypeError, KeyError) as exc:
        db.session.rollback()
        return error(str(exc))
    except IntegrityError:
        db.session.rollback()
        return error("Import failed because a duplicate or invalid record was found. No rows were imported.", "conflict", 409)


@api_v1_bp.get("/settings")
def settings():
    return response({"frontend_origin": current_app.config["FRONTEND_ORIGIN"], "max_upload_bytes": current_app.config["MAX_CONTENT_LENGTH"]})
