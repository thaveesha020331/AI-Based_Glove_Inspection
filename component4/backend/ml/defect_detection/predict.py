"""Reusable and command-line inference for the glove defect YOLO model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "weight" / "best.pt"


class DefectDetector:
    """Load an Ultralytics checkpoint once and run low-latency frame inference."""

    def __init__(self, model_path=DEFAULT_MODEL_PATH, confidence=0.50, image_size=640):
        self.model_path = Path(model_path)
        self.confidence = float(confidence)
        self.image_size = int(image_size)
        self._model = None

    def load(self):
        if self._model is not None:
            return self
        if not self.model_path.is_file():
            raise FileNotFoundError(f"Defect model not found: {self.model_path}")
        try:
            from ultralytics import YOLO
        except ImportError as error:
            raise RuntimeError(
                "Ultralytics is not installed. Install component4/backend/requirements.txt."
            ) from error
        self._model = YOLO(str(self.model_path))
        return self

    def predict(self, source, annotate=False):
        self.load()
        result = self._model.predict(
            source=source,
            conf=self.confidence,
            imgsz=self.image_size,
            device="cpu",
            verbose=False,
            max_det=20,
        )[0]
        detections = []
        boxes = result.boxes
        if boxes is not None:
            for class_id, confidence, coordinates in zip(
                boxes.cls.cpu().tolist(),
                boxes.conf.cpu().tolist(),
                boxes.xyxy.cpu().tolist(),
            ):
                class_index = int(class_id)
                detections.append(
                    {
                        "class_id": class_index,
                        "category": str(result.names.get(class_index, class_index)),
                        "confidence": round(float(confidence), 4),
                        "box": [round(float(value), 1) for value in coordinates],
                    }
                )
        detections.sort(key=lambda item: item["confidence"], reverse=True)
        primary = detections[0] if detections else None
        return {
            "defective": bool(detections),
            "category": primary["category"] if primary else None,
            "confidence": primary["confidence"] if primary else None,
            "detections": detections,
            "annotated_frame": result.plot() if annotate else None,
        }


def main():
    parser = argparse.ArgumentParser(description="Detect glove defects in an image.")
    parser.add_argument("image", type=Path)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--confidence", type=float, default=0.50)
    parser.add_argument("--image-size", type=int, default=640)
    args = parser.parse_args()
    prediction = DefectDetector(
        args.model, confidence=args.confidence, image_size=args.image_size
    ).predict(str(args.image))
    prediction.pop("annotated_frame", None)
    print(json.dumps(prediction, indent=2))


if __name__ == "__main__":
    main()
