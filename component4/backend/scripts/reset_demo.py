"""Remove only demonstration rows created by the local seed workflow."""

from app import create_app, db
from app.models import Batch, InspectionRecord, ProductionRecord, QualityRecord, SortingRecord


def reset_demo() -> None:
    app = create_app()
    with app.app_context():
        demo_batches = db.session.query(Batch.batch_id).filter(
            Batch.metadata_json["demonstration"].as_boolean().is_(True)
        ).all()
        batch_ids = [batch_id for (batch_id,) in demo_batches]
        if not batch_ids:
            print("No demonstration data found.")
            return
        for model in (InspectionRecord, ProductionRecord, QualityRecord, SortingRecord):
            db.session.query(model).filter(model.batch_id.in_(batch_ids)).delete(synchronize_session=False)
        db.session.query(Batch).filter(Batch.batch_id.in_(batch_ids)).delete(synchronize_session=False)
        db.session.commit()
        print(f"Removed {len(batch_ids)} demonstration batch(es).")


if __name__ == "__main__":
    reset_demo()
