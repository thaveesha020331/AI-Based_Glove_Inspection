from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class DetectionUnavailable(RuntimeError):
    pass


class DefectDetector:
    """Ultralytics adapter. No detections are fabricated when the model is absent."""

    def __init__(self, model_path: str | None = None):
        self.model_path = Path(model_path or os.getenv("DEFECT_MODEL_PATH", ""))
        self._model = None

    @property
    def available(self) -> bool:
        return self.model_path.is_file()

    def status(self) -> dict[str, Any]:
        dependency_error = None
        try:
            import torch  # noqa: F401
            from ultralytics import YOLO  # noqa: F401
        except ImportError as exc:
            dependency_error = f"{type(exc).__name__}: {exc}"
        return {
            "weights_available": self.model_path.is_file(),
            "runtime_available": dependency_error is None,
            "ready": self.model_path.is_file() and dependency_error is None,
            "model_path": str(self.model_path),
            "dependency_error": dependency_error,
        }

    def _load(self):
        readiness = self.status()
        if not readiness["weights_available"]:
            raise DetectionUnavailable(
                "No trained defect model is configured. Install ultralytics and run "
                "python -m ml.quality_detection.train before inference."
            )
        if not readiness["runtime_available"]:
            raise DetectionUnavailable(
                "Defect weights exist, but the inference runtime is unavailable: "
                f"{readiness['dependency_error']}. Use Python 3.12-3.14 with a "
                "compatible PyTorch and Ultralytics installation."
            )
        if self._model is None:
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise DetectionUnavailable(
                    "Ultralytics is not installed. Install backend requirements with "
                    "the detection extras before inference."
                ) from exc
            self._model = YOLO(str(self.model_path))
        return self._model

    def predict(self, image_path: Path, confidence: float = 0.25) -> dict[str, Any]:
        model = self._load()
        result = model.predict(source=str(image_path), conf=confidence, verbose=False)[0]
        names = result.names
        detections = []
        for box in result.boxes:
            xyxy = [round(float(value), 2) for value in box.xyxy[0].tolist()]
            detections.append({
                "class_id": int(box.cls[0]),
                "class": str(names[int(box.cls[0])]),
                "confidence": round(float(box.conf[0]), 5),
                "bbox": xyxy,
                "area_zone": anatomical_region(xyxy, result.orig_shape[1], result.orig_shape[0]),
            })
        annotated = result.plot()
        annotated_path = image_path.with_name(f"{image_path.stem}_annotated.jpg")
        from PIL import Image
        Image.fromarray(annotated[:, :, ::-1]).save(annotated_path, quality=90)
        return {
            "detections": detections,
            "annotated_path": annotated_path,
            "width": int(result.orig_shape[1]),
            "height": int(result.orig_shape[0]),
        }


def normalized_zone(bbox: list[float], width: int, height: int) -> str:
    """Image-based zone only; the dataset has no verified anatomical labels."""
    center_x = ((bbox[0] + bbox[2]) / 2) / max(width, 1)
    center_y = ((bbox[1] + bbox[3]) / 2) / max(height, 1)
    vertical = "top" if center_y < 1 / 3 else "bottom" if center_y >= 2 / 3 else "middle"
    horizontal = "left" if center_x < 1 / 3 else "right" if center_x >= 2 / 3 else "center"
    return f"{vertical}-{horizontal}"


def anatomical_region(bbox: list[float], width: int, height: int) -> str:
    """Map the supplied landscape dataset framing to broad glove regions.

    The dataset consistently shows the cuff at the left, palm in the middle,
    and fingers at the right. This is an image-coordinate heuristic, not a
    learned anatomical classifier and cannot identify an individual finger.
    """
    center_x = ((bbox[0] + bbox[2]) / 2) / max(width, 1)
    if width / max(height, 1) < 1.3:
        return normalized_zone(bbox, width, height)
    if center_x < 0.28:
        return "wrist/cuff"
    if center_x < 0.62:
        return "palm"
    return "finger region"
