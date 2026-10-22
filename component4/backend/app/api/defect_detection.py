from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image

from app import db
from app.models.entities import Batch, DefectDetection, DefectImage
from app.services.defect_detection import DefectDetector, DetectionUnavailable, anatomical_region

defect_bp = Blueprint("defect_detection", __name__)
ALLOWED = {"jpg", "jpeg", "png", "webp"}


def error(message: str, code: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def detector() -> DefectDetector:
    configured = current_app.config.get("DEFECT_MODEL_PATH")
    return current_app.extensions.setdefault("defect_detector", DefectDetector(configured))


def analyse(path: Path):
    try:
        return detector().predict(path)
    except DetectionUnavailable as exc:
        raise ValueError(str(exc)) from exc


@defect_bp.post("/predict")
def predict():
    uploaded = request.files.get("image")
    if uploaded is None or not uploaded.filename:
        return error("Upload an image in the 'image' field.", "missing_image", 400)
    suffix = Path(uploaded.filename).suffix.lower().lstrip(".")
    if suffix not in ALLOWED:
        return error("Only JPG, JPEG, PNG, and WEBP images are accepted.", "invalid_file_type", 415)
    upload_dir = Path(current_app.config["DEFECT_UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / f"{uuid.uuid4().hex}.{suffix}"
    uploaded.save(path)
    try:
        with Image.open(path) as image:
            image.verify()
        result = analyse(path)
    except (OSError, ValueError) as exc:
        path.unlink(missing_ok=True)
        code = "model_unavailable" if isinstance(exc, ValueError) else "invalid_image"
        status = 503 if code == "model_unavailable" else 422
        return error(str(exc), code, status)
    result["annotated_url"] = f"/api/defect-files/{result['annotated_path'].name}"
    result.pop("annotated_path", None)
    result["counts"] = dict(Counter(item["class"] for item in result["detections"]))
    return jsonify({"data": result})


@defect_bp.get("/model/status")
def model_status():
    return jsonify({"data": detector().status()})


@defect_bp.post("/batches")
def create_batch():
    payload = request.get_json(silent=True) or {}
    batch_id = str(payload.get("batch_id", "")).strip() or f"DEMO-{uuid.uuid4().hex[:8].upper()}"
    if len(batch_id) > 64 or Batch.query.get(batch_id):
        return error("batch_id must be unique and no longer than 64 characters.", "invalid_batch_id", 409)
    batch = Batch(batch_id=batch_id, production_date=datetime.now(timezone.utc),
                  production_line=payload.get("production_line"), metadata_json={"source": "image_batch"})
    db.session.add(batch)
    db.session.commit()
    return jsonify({"data": {"batch_id": batch_id}}), 201


@defect_bp.get("/dataset")
def dataset_info():
    from ml.quality_detection.validate_coco import validate
    dataset_root = Path(current_app.config["DEFECT_DATASET_DIR"])
    if not dataset_root.is_dir():
        return error("Configured defect dataset directory does not exist.", "dataset_unavailable", 503)
    return jsonify({"data": validate(dataset_root)})


@defect_bp.get("/dataset/preview")
def dataset_preview():
    """Return a ground-truth COCO preview, never presented as model inference."""
    split = request.args.get("split", "test")
    if split not in {"train", "valid", "test"}:
        return error("split must be train, valid, or test.", "invalid_split", 400)
    annotation_file = Path(current_app.config["DEFECT_DATASET_DIR"]) / split / "_annotations.coco.json"
    if not annotation_file.is_file():
        return error("The configured COCO annotation file does not exist.", "dataset_unavailable", 503)
    data = json.loads(annotation_file.read_text(encoding="utf-8"))
    categories = {item["id"]: item["name"] for item in data.get("categories", [])}
    images = {item["id"]: item for item in data.get("images", [])}
    counts = Counter()
    zones = Counter()
    by_image = Counter()
    for annotation in data.get("annotations", []):
        name = categories.get(annotation["category_id"], "Unknown defect")
        counts[name] += 1
        by_image[annotation["image_id"]] += 1
        image = images.get(annotation["image_id"], {})
        width, height = image.get("width", 0), image.get("height", 0)
        x, y, box_width, box_height = annotation["bbox"]
        zones[anatomical_region(
            [x, y, x + box_width, y + box_height], width, height
        )] += 1
    image_rows = [{"filename": image["file_name"], "detection_count": by_image[image["id"]]}
                  for image in images.values()]
    image_rows.sort(key=lambda item: (-item["detection_count"], item["filename"]))
    return jsonify({"data": {
        "mode": "COCO ground-truth audit preview",
        "split": split,
        "total_images_inspected": len(images),
        "total_detected_defects": sum(counts.values()),
        "defect_counts": dict(counts),
        "affected_images": sum(bool(count) for count in by_image.values()),
        "affected_image_percentage": round(sum(bool(count) for count in by_image.values()) / len(images) * 100, 2) if images else 0,
        "average_detection_confidence": None,
        "quality_status": "ANNOTATION AUDIT",
        "quality_explanation": "Counts come from supplied COCO bounding boxes; no model confidence is available.",
        "affected_area_ranking": [{"area": area, "count": count} for area, count in zones.most_common()],
        "most_affected_area": ({"area": zones.most_common(1)[0][0], "count": zones.most_common(1)[0][1]} if zones else None),
        "images": image_rows,
        "location_method": "Broad anatomical heuristic from the consistent dataset framing: left=cuff, center=palm, right=finger region.",
        "limitation": "The location is an image-coordinate heuristic, not a learned anatomical classifier; individual fingers cannot be identified.",
    }})


@defect_bp.get("/training/status")
def training_status():
    model_path = Path(current_app.config["DEFECT_MODEL_PATH"])
    metadata_path = model_path.with_suffix(".metrics.json")
    return jsonify({"data": {
        "model_available": model_path.is_file(),
        "model_path": str(model_path),
        "metrics_available": metadata_path.is_file(),
        "metrics": json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else None,
    }})


@defect_bp.post("/batches/<string:batch_id>/images")
def upload_batch_images(batch_id: str):
    if not Batch.query.get(batch_id):
        return error("Batch does not exist.", "batch_not_found", 404)
    files = request.files.getlist("images") or ([request.files["image"]] if "image" in request.files else [])
    if not files:
        return error("Upload one or more images using 'images'.", "missing_images", 400)
    results = []
    upload_dir = Path(current_app.config["DEFECT_UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    for uploaded in files:
        suffix = Path(uploaded.filename or "").suffix.lower().lstrip(".")
        if suffix not in ALLOWED:
            return error(f"Unsupported image type: {uploaded.filename}", "invalid_file_type", 415)
        image_id = uuid.uuid4().hex
        path = upload_dir / f"{image_id}.{suffix}"
        uploaded.save(path)
        try:
            with Image.open(path) as image:
                result = analyse(path)
                width, height = image.size
        except (OSError, ValueError) as exc:
            path.unlink(missing_ok=True)
            return error(str(exc), "analysis_failed", 422)
        record = DefectImage(image_id=image_id, batch_id=batch_id,
            original_filename=secure_filename(uploaded.filename or path.name),
            stored_path=str(path), width=width, height=height,
            detection_count=len(result["detections"]), analysis_json={"counts": dict(Counter(x["class"] for x in result["detections"]))})
        db.session.add(record)
        db.session.flush()
        for item in result["detections"]:
            db.session.add(DefectDetection(image_id=image_id, category=item["class"], confidence=item["confidence"],
                x1=item["bbox"][0], y1=item["bbox"][1], x2=item["bbox"][2], y2=item["bbox"][3], area_zone=item["area_zone"]))
        results.append({"image_id": image_id, "filename": record.original_filename, "detections": result["detections"],
                        "annotated_url": f"/api/defect-files/{result['annotated_path'].name}"})
    db.session.commit()
    return jsonify({"data": results}), 201


@defect_bp.get("/batches")
def list_batches():
    rows = Batch.query.filter(Batch.metadata_json["source"].as_string() == "image_batch").order_by(Batch.created_at.desc()).all()
    return jsonify({"data": [{"batch_id": x.batch_id, "created_at": x.created_at.isoformat()} for x in rows]})


@defect_bp.get("/batches/<string:batch_id>/summary")
def summary(batch_id: str):
    if not Batch.query.get(batch_id):
        return error("Batch does not exist.", "batch_not_found", 404)
    images = DefectImage.query.filter_by(batch_id=batch_id).all()
    image_ids = [x.image_id for x in images]
    detections = DefectDetection.query.filter(DefectDetection.image_id.in_(image_ids)).all() if image_ids else []
    counts = Counter(x.category for x in detections)
    zones = {}
    for zone in sorted({x.area_zone for x in detections}):
        zone_detections = [x for x in detections if x.area_zone == zone]
        zones[zone] = {
            "count": len(zone_detections),
            "confidence_weighted_score": round(sum(float(x.confidence) for x in zone_detections), 5),
            "affected_images": len({x.image_id for x in zone_detections}),
        }
    ranked = [{"area": area, **stats} for area, stats in sorted(
        zones.items(), key=lambda item: (-item[1]["count"], -item[1]["confidence_weighted_score"], item[0])
    )]
    affected_images = len({x.image_id for x in detections})
    total_confidence = sum(float(x.confidence) for x in detections)
    defect_rate = affected_images / len(images) * 100 if images else 0
    total_defects = len(detections)
    reject_threshold = int(current_app.config["DEFECT_REJECT_COUNT"])
    review_threshold = int(current_app.config["DEFECT_REVIEW_COUNT"])
    if total_defects >= reject_threshold:
        quality_status, quality_explanation = "REJECT", f"{total_defects} observed detections meet the reject threshold of {reject_threshold}."
    elif total_defects >= review_threshold:
        quality_status, quality_explanation = "REVIEW", f"{total_defects} observed detections meet the review threshold of {review_threshold}."
    else:
        quality_status, quality_explanation = "ACCEPT", f"{total_defects} observed detections are below the review threshold of {review_threshold}."
    return jsonify({"data": {"batch_id": batch_id, "image_based_analysis": True,
        "location_method": "Broad anatomical heuristic for the supplied landscape glove framing; other aspect ratios use normalized image zones.",
        "limitation": "The location is an image-coordinate heuristic, not a learned anatomical classifier; individual fingers cannot be identified.",
        "total_images_inspected": len(images), "total_detected_defects": len(detections),
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "defect_counts": dict(counts), "affected_images": affected_images,
        "affected_image_percentage": round(defect_rate, 2),
        "average_detection_confidence": round(total_confidence / total_defects, 5) if total_defects else None,
        "quality_status": quality_status, "quality_explanation": quality_explanation,
        "affected_area_ranking": ranked,
        "most_affected_area": ranked[0] if ranked else None,
        "images": sorted(
            [{"image_id": x.image_id, "filename": x.original_filename, "detection_count": x.detection_count} for x in images],
            key=lambda item: (-item["detection_count"], item["filename"]),
        )}})


@defect_bp.get("/analytics/overview")
def overview():
    detections = DefectDetection.query.all()
    return jsonify({"data": {"total_images_inspected": DefectImage.query.count(),
        "total_detected_defects": len(detections), "defect_counts": dict(Counter(x.category for x in detections)),
        "batches_analysed": Batch.query.filter(Batch.metadata_json["source"].as_string() == "image_batch").count()}})


@defect_bp.get("/defect-files/<path:filename>")
def defect_file(filename: str):
    return send_from_directory(current_app.config["DEFECT_UPLOAD_DIR"], filename)
