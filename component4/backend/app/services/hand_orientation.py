"""Supporting left/right glove orientation classifier.

This model is intentionally separate from the tabular production quality-risk
model. Its label is image orientation only and must not be interpreted as a
defect or acceptance label.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import joblib
import numpy as np
from PIL import Image, UnidentifiedImageError
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
CLASS_NAMES = ("left", "right")
MODEL_FILENAME = "hand_orientation.joblib"
METADATA_FILENAME = "hand_orientation.json"


@dataclass(frozen=True)
class OrientationConfig:
    image_size: tuple[int, int] = (64, 64)
    random_state: int = 42
    test_size: float = 0.2
    validation_size: float = 0.2
    near_duplicate_distance: int = 2


def _capture_group(path: Path) -> str:
    """Group adjacent camera captures by date/hour/minute from WIN filenames."""
    match = re.match(r"^(WIN_\d{8}_\d{2}_\d{2})", path.stem, re.IGNORECASE)
    return match.group(1) if match else path.stem


def _feature_vector(path: Path, image_size: tuple[int, int]) -> np.ndarray:
    try:
        with Image.open(path) as image:
            image = image.convert("L").resize(image_size, Image.Resampling.BILINEAR)
            pixels = np.asarray(image, dtype=np.float32) / 255.0
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError(f"Unable to read image '{path.name}': {exc}") from exc
    gradients_x = np.diff(pixels, axis=1, prepend=pixels[:, :1])
    gradients_y = np.diff(pixels, axis=0, prepend=pixels[:1, :])
    gradients = np.sqrt(gradients_x ** 2 + gradients_y ** 2)
    return np.concatenate((pixels.ravel(), gradients.ravel())).astype(np.float32)


def _perceptual_hash(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        pixels = np.asarray(image.convert("L").resize((8, 8), Image.Resampling.BILINEAR), dtype=np.float32)
    return pixels >= pixels.mean()


def discover_dataset(dataset_dir: str | Path) -> dict[str, Any]:
    root = Path(dataset_dir)
    files: list[Path] = []
    labels: list[str] = []
    for label in CLASS_NAMES:
        class_dir = root / label
        for path in sorted(class_dir.rglob("*")) if class_dir.exists() else []:
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(path)
                labels.append(label)
    if not files:
        raise ValueError(f"No supported images found under '{root}'. Expected left and right folders.")

    hashes: list[np.ndarray] = []
    dimensions: dict[str, int] = {}
    for path in files:
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                dimensions[f"{image.width}x{image.height}"] = dimensions.get(
                    f"{image.width}x{image.height}", 0
                ) + 1
            hashes.append(_perceptual_hash(path))
        except (OSError, UnidentifiedImageError) as exc:
            raise ValueError(f"Invalid image '{path}': {exc}") from exc

    near_duplicate_groups = 0
    for index, current in enumerate(hashes):
        if any(np.count_nonzero(current != previous) <= 2 for previous in hashes[:index]):
            near_duplicate_groups += 1
    counts = {label: labels.count(label) for label in CLASS_NAMES}
    return {
        "dataset_dir": str(root),
        "image_count": len(files),
        "class_distribution": counts,
        "dimensions": dimensions,
        "corrupt_count": 0,
        "near_duplicate_file_count": near_duplicate_groups,
        "files": files,
        "labels": np.asarray(labels),
        "groups": np.asarray([_capture_group(path) for path in files]),
    }


def _split_indices(labels: np.ndarray, groups: np.ndarray, config: OrientationConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    indices = np.arange(len(labels))
    for seed in range(config.random_state, config.random_state + 25):
        first = next(GroupShuffleSplit(n_splits=1, test_size=config.test_size, random_state=seed).split(indices, labels, groups))
        train_val, test = first
        second = next(GroupShuffleSplit(n_splits=1, test_size=0.5, random_state=seed + 100).split(
            train_val, labels[train_val], groups[train_val]
        ))
        train, validation = train_val[second[0]], train_val[second[1]]
        if all(len(np.unique(labels[index])) == 2 for index in (train, validation, test)):
            return train, validation, test
    raise ValueError("Unable to create grouped train/validation/test splits containing both classes.")


def _metrics(labels: np.ndarray, predictions: np.ndarray) -> dict[str, Any]:
    return {
        "sample_size": int(len(labels)),
        "accuracy": round(float(accuracy_score(labels, predictions)), 4),
        "precision": round(float(precision_score(labels, predictions, pos_label="right", zero_division=0)), 4),
        "recall": round(float(recall_score(labels, predictions, pos_label="right", zero_division=0)), 4),
        "f1": round(float(f1_score(labels, predictions, pos_label="right", zero_division=0)), 4),
        "confusion_matrix": confusion_matrix(labels, predictions, labels=list(CLASS_NAMES)).tolist(),
    }


class HandOrientationService:
    def __init__(self, artifact_dir: str | Path, config: OrientationConfig | None = None):
        self.artifact_dir = Path(artifact_dir)
        self.config = config or OrientationConfig()
        self.artifact_path = self.artifact_dir / MODEL_FILENAME
        self.metadata_path = self.artifact_dir / METADATA_FILENAME

    def status(self) -> dict[str, Any]:
        if not self.artifact_path.exists() or not self.metadata_path.exists():
            return {"trained": False, "state": "untrained", "message": "No glove-orientation model is available."}
        try:
            return {"trained": True, "state": "ready", **json.loads(self.metadata_path.read_text(encoding="utf-8"))}
        except (OSError, json.JSONDecodeError) as exc:
            return {"trained": False, "state": "failed", "message": f"Model metadata cannot be read: {exc}"}

    def train(self, dataset_dir: str | Path) -> dict[str, Any]:
        audit = discover_dataset(dataset_dir)
        files = audit["files"]
        labels = audit["labels"]
        train, validation, test = _split_indices(labels, audit["groups"], self.config)
        features = np.vstack([_feature_vector(path, self.config.image_size) for path in files])
        pipeline = Pipeline([
            ("scale", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=1000, random_state=self.config.random_state)),
        ])
        pipeline.fit(features[train], labels[train])
        validation_metrics = _metrics(labels[validation], pipeline.predict(features[validation]))
        test_metrics = _metrics(labels[test], pipeline.predict(features[test]))
        metadata = {
            "model_version": "orientation-logistic-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "purpose": "left/right glove orientation classification only",
            "dataset": {key: value for key, value in audit.items() if key not in {"files", "labels", "groups"}},
            "split": {"strategy": "grouped capture-minute split", "train": len(train), "validation": len(validation), "test": len(test)},
            "preprocessing": {"image_size": list(self.config.image_size), "grayscale": True, "features": "pixels plus gradient magnitude"},
            "evaluation": {"validation": validation_metrics, "test": test_metrics},
        }
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, self.artifact_path)
        self.metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return {"state": "ready", "trained": True, **metadata}

    def predict(self, image_path: str | Path) -> dict[str, Any]:
        if not self.artifact_path.exists():
            return {"state": "unavailable", "message": "The orientation model is untrained."}
        path = Path(image_path)
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return {"state": "invalid_input", "message": "A valid supported image file is required."}
        try:
            pipeline = joblib.load(self.artifact_path)
            features = _feature_vector(path, self.config.image_size).reshape(1, -1)
            probabilities = pipeline.predict_proba(features)[0]
            classes = pipeline.named_steps["classifier"].classes_
            index = int(np.argmax(probabilities))
            return {
                "state": "ready",
                "label": str(classes[index]),
                "probability": round(float(probabilities[index]), 4),
                "model_version": self.status().get("model_version"),
                "purpose": "orientation only; not a glove defect or quality prediction",
            }
        except (OSError, ValueError, KeyError, AttributeError) as exc:
            return {"state": "failed", "message": f"Unable to predict this image: {exc}"}
