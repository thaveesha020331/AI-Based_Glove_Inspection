from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, Index, Numeric, Text
from sqlalchemy.types import JSON

from app import db


def utcnow():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Batch(TimestampMixin, db.Model):
    __tablename__ = "batches"
    batch_id = db.Column(db.String(64), primary_key=True)
    production_date = db.Column(db.DateTime(timezone=True), nullable=False)
    production_line = db.Column(db.String(100))
    current_quality_status = db.Column(db.String(20), nullable=False, default="Pending")
    metadata_json = db.Column(JSON, nullable=False, default=dict)
    __table_args__ = (Index("ix_batches_production_date", "production_date"),)


class ProductionRecord(TimestampMixin, db.Model):
    __tablename__ = "production_records"
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(64), db.ForeignKey("batches.batch_id"), nullable=False)
    production_timestamp = db.Column(db.DateTime(timezone=True), nullable=False)
    production_quantity = db.Column(db.Integer, nullable=False)
    inspected_quantity = db.Column(db.Integer, nullable=False, default=0)
    accepted_quantity = db.Column(db.Integer, nullable=False, default=0)
    rejected_quantity = db.Column(db.Integer, nullable=False, default=0)
    metadata_json = db.Column(JSON, nullable=False, default=dict)
    __table_args__ = (
        CheckConstraint("production_quantity >= 0 AND inspected_quantity >= 0 AND accepted_quantity >= 0 AND rejected_quantity >= 0", name="ck_production_nonnegative"),
        CheckConstraint("inspected_quantity <= production_quantity AND accepted_quantity + rejected_quantity <= inspected_quantity", name="ck_production_consistent"),
        Index("ix_production_batch_timestamp", "batch_id", "production_timestamp"),
    )


class InspectionRecord(TimestampMixin, db.Model):
    __tablename__ = "inspection_records"
    record_id = db.Column(db.String(64), primary_key=True)
    batch_id = db.Column(db.String(64), db.ForeignKey("batches.batch_id"), nullable=False)
    defect_category = db.Column(db.String(100), nullable=False)
    defect_status = db.Column(db.String(30), nullable=False)
    anomaly_score = db.Column(Numeric(8, 5))
    confidence = db.Column(Numeric(8, 5))
    inspection_timestamp = db.Column(db.DateTime(timezone=True), nullable=False)
    metadata_json = db.Column(JSON, nullable=False, default=dict)
    __table_args__ = (
        CheckConstraint("anomaly_score IS NULL OR (anomaly_score >= 0 AND anomaly_score <= 1)", name="ck_inspection_anomaly"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_inspection_confidence"),
        Index("ix_inspection_batch_timestamp", "batch_id", "inspection_timestamp"),
        Index("ix_inspection_category", "defect_category"),
    )


class QualityRecord(TimestampMixin, db.Model):
    __tablename__ = "quality_records"
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(64), db.ForeignKey("batches.batch_id"), nullable=False)
    glove_size = db.Column(db.String(20), nullable=False)
    colour = db.Column(db.String(50), nullable=False)
    length_measurement = db.Column(Numeric(8, 3), nullable=False)
    orientation = db.Column(db.String(10), nullable=False)
    quality_grade = db.Column(db.String(10), nullable=False)
    batch_consistency_status = db.Column(db.String(30), nullable=False)
    metadata_json = db.Column(JSON, nullable=False, default=dict)
    __table_args__ = (
        CheckConstraint("length_measurement >= 0", name="ck_quality_length"),
        CheckConstraint("orientation IN ('Left', 'Right')", name="ck_quality_orientation"),
        CheckConstraint("quality_grade IN ('A', 'B', 'C', 'Reject')", name="ck_quality_grade"),
        Index("ix_quality_batch_grade", "batch_id", "quality_grade"),
    )


class SortingRecord(TimestampMixin, db.Model):
    __tablename__ = "sorting_records"
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(64), db.ForeignKey("batches.batch_id"), nullable=False)
    intended_sorting_category = db.Column(db.String(100), nullable=False)
    actual_sorting_outcome = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    sorting_timestamp = db.Column(db.DateTime(timezone=True), nullable=False)
    metadata_json = db.Column(JSON, nullable=False, default=dict)
    __table_args__ = (Index("ix_sorting_batch_timestamp", "batch_id", "sorting_timestamp"),)


class QualityAlert(TimestampMixin, db.Model):
    __tablename__ = "quality_alerts"
    id = db.Column(db.Integer, primary_key=True)
    severity = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(Text, nullable=False)
    batch_id = db.Column(db.String(64), db.ForeignKey("batches.batch_id"))
    triggering_metric = db.Column(db.String(100), nullable=False)
    observed_value = db.Column(Numeric(12, 5))
    threshold_or_risk_context = db.Column(Text)
    recommendation = db.Column(Text)
    status = db.Column(db.String(20), nullable=False, default="Open")
    __table_args__ = (Index("ix_alert_status_severity", "status", "severity"),)


class PredictionRecord(TimestampMixin, db.Model):
    __tablename__ = "prediction_records"
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(64), db.ForeignKey("batches.batch_id"), nullable=False)
    predicted_risk_category = db.Column(db.String(30), nullable=False)
    predicted_probability = db.Column(Numeric(8, 5))
    model_version = db.Column(db.String(100), nullable=False)
    prediction_time = db.Column(db.DateTime(timezone=True), nullable=False)
    prediction_status = db.Column(db.String(30), nullable=False, default="Completed")
    __table_args__ = (
        CheckConstraint("predicted_probability IS NULL OR (predicted_probability >= 0 AND predicted_probability <= 1)", name="ck_prediction_probability"),
        Index("ix_prediction_batch_time", "batch_id", "prediction_time"),
    )


class ReportRecord(TimestampMixin, db.Model):
    __tablename__ = "report_records"
    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(50), nullable=False)
    parameters = db.Column(JSON, nullable=False, default=dict)
    status = db.Column(db.String(30), nullable=False, default="Queued")
    file_reference = db.Column(db.String(500))


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.String(100))
    details = db.Column(JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (Index("ix_audit_created_at", "created_at"),)


class DefectImage(TimestampMixin, db.Model):
    __tablename__ = "defect_images"
    image_id = db.Column(db.String(64), primary_key=True)
    batch_id = db.Column(db.String(64), db.ForeignKey("batches.batch_id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    detection_count = db.Column(db.Integer, nullable=False, default=0)
    analysis_json = db.Column(JSON, nullable=False, default=dict)
    __table_args__ = (Index("ix_defect_images_batch", "batch_id"),)


class DefectDetection(db.Model):
    __tablename__ = "defect_detections"
    id = db.Column(db.Integer, primary_key=True)
    image_id = db.Column(db.String(64), db.ForeignKey("defect_images.image_id"), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    confidence = db.Column(Numeric(8, 5), nullable=False)
    x1 = db.Column(db.Float, nullable=False)
    y1 = db.Column(db.Float, nullable=False)
    x2 = db.Column(db.Float, nullable=False)
    y2 = db.Column(db.Float, nullable=False)
    area_zone = db.Column(db.String(30), nullable=False)
    __table_args__ = (Index("ix_defect_detections_image", "image_id"),)


def model_to_dict(model):
    result = {}
    for column in model.__table__.columns:
        value = getattr(model, column.name)
        if isinstance(value, Decimal):
            value = float(value)
        if isinstance(value, datetime):
            value = value.isoformat()
        result[column.name] = value
    return result
