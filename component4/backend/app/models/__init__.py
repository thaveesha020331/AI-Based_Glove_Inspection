"""SQLAlchemy entities for the GloveIQ persistence layer."""

from app.models.entities import (
    AuditLog,
    Batch,
    InspectionRecord,
    PredictionRecord,
    ProductionRecord,
    QualityAlert,
    QualityRecord,
    ReportRecord,
    SortingRecord,
    DefectImage,
    DefectDetection,
)

__all__ = [
    "AuditLog", "Batch", "InspectionRecord", "PredictionRecord",
    "ProductionRecord", "QualityAlert", "QualityRecord", "ReportRecord",
    "SortingRecord",
    "DefectImage", "DefectDetection",
]
