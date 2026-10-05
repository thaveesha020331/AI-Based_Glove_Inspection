"""Insert clearly marked demonstration data for local development."""

from datetime import datetime, timezone

from app import create_app, db
from app.models import Batch, InspectionRecord, ProductionRecord, QualityRecord


def seed():
    app = create_app()
    with app.app_context():
        if db.session.get(Batch, "DEMO-2026-001"):
            print("Demo data already exists.")
            return
        timestamp = datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc)
        db.session.add(Batch(
            batch_id="DEMO-2026-001", production_date=timestamp,
            production_line="Demo Line", current_quality_status="A",
            metadata_json={"demonstration": True},
        ))
        db.session.add(ProductionRecord(
            batch_id="DEMO-2026-001", production_timestamp=timestamp,
            production_quantity=1000, inspected_quantity=980,
            accepted_quantity=950, rejected_quantity=30,
            metadata_json={"demonstration": True},
        ))
        db.session.add(InspectionRecord(
            record_id="DEMO-INS-001", batch_id="DEMO-2026-001",
            defect_category="Pinhole", defect_status="Detected",
            anomaly_score=0.82, confidence=0.96,
            inspection_timestamp=timestamp,
            metadata_json={"demonstration": True},
        ))
        db.session.add(QualityRecord(
            batch_id="DEMO-2026-001", glove_size="M", colour="Blue",
            length_measurement=245.5, orientation="Left",
            quality_grade="A", batch_consistency_status="Consistent",
            metadata_json={"demonstration": True},
        ))
        db.session.commit()
        print("Inserted demonstration batch DEMO-2026-001.")


if __name__ == "__main__":
    seed()
