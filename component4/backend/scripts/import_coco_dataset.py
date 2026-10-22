"""Import truthful COCO dataset audit records for a local presentation database."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app import create_app, db
from app.models import Batch, InspectionRecord, ProductionRecord, QualityRecord

SOURCE = "coco_dataset_audit"
CATEGORY_NAMES = {0: "Other defect", 1: "Pinhole", 2: "Tear", 3: "Other defect"}


def import_dataset(dataset_root: Path) -> int:
    created = 0
    for split in ("train", "valid", "test"):
        data = json.loads(
            (dataset_root / split / "_annotations.coco.json").read_text(encoding="utf-8")
        )
        batch_id = f"DATASET-{split.upper()}"
        existing = db.session.get(Batch, batch_id)
        if existing:
            InspectionRecord.query.filter_by(batch_id=batch_id).delete()
            QualityRecord.query.filter_by(batch_id=batch_id).delete()
            ProductionRecord.query.filter_by(batch_id=batch_id).delete()
            batch = existing
        else:
            batch = Batch(batch_id=batch_id)
            db.session.add(batch)
        timestamp = datetime.now(timezone.utc)
        annotations = data["annotations"]
        counts = Counter(
            CATEGORY_NAMES.get(item["category_id"], "Unknown defect")
            for item in annotations
        )
        batch.production_date = timestamp
        batch.production_line = f"COCO {split}"
        batch.current_quality_status = "Dataset proxy"
        batch.metadata_json = {
            "source": SOURCE,
            "split": split,
            "note": "Quality is a deterministic proxy from COCO annotations, not a factory release grade or model prediction.",
            "category_counts": dict(counts),
        }
        annotations_by_image = {}
        for annotation in annotations:
            annotations_by_image.setdefault(annotation["image_id"], []).append(annotation)
        image_count = len(data["images"])
        affected_images = sum(bool(annotations_by_image.get(image["id"])) for image in data["images"])
        db.session.add(ProductionRecord(
            batch_id=batch_id,
            production_timestamp=timestamp,
            production_quantity=image_count,
            inspected_quantity=image_count,
            accepted_quantity=image_count - affected_images,
            rejected_quantity=affected_images,
            metadata_json={"source": SOURCE, "unit": "dataset images", "quality_proxy": True},
        ))
        for image in data["images"]:
            image_annotations = annotations_by_image.get(image["id"], [])
            count = len(image_annotations)
            grade = "A" if count == 0 else "B" if count <= 2 else "Reject"
            db.session.add(QualityRecord(
                batch_id=batch_id,
                glove_size="Unknown",
                colour="Unknown",
                length_measurement=0,
                orientation="Left",
                quality_grade=grade,
                batch_consistency_status="Dataset annotation proxy",
                metadata_json={
                    "source": SOURCE,
                    "image_id": image["id"],
                    "file_name": image["file_name"],
                    "annotation_count": count,
                    "quality_proxy": True,
                },
            ))
        for index, annotation in enumerate(annotations):
            db.session.add(InspectionRecord(
                record_id=f"DATASET-{split.upper()}-{annotation['id']}-{index}",
                batch_id=batch_id,
                defect_category=CATEGORY_NAMES.get(
                    annotation["category_id"], "Unknown defect"
                ),
                defect_status="Annotated",
                confidence=None,
                anomaly_score=None,
                inspection_timestamp=timestamp,
                metadata_json={
                    "source": SOURCE,
                    "annotation_id": annotation["id"],
                    "image_id": annotation["image_id"],
                    "bbox": annotation["bbox"],
                },
            ))
        created += 1
    db.session.commit()
    return created


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=Path(__file__).parents[2] / "dataset"
    )
    args = parser.parse_args()
    if not args.dataset.is_dir():
        raise SystemExit(f"Dataset directory not found: {args.dataset}")
    app = create_app()
    with app.app_context():
        print(f"Created {import_dataset(args.dataset)} dataset audit batches.")
        print("No model predictions, quality grades, or factory quantities were invented.")


if __name__ == "__main__":
    main()
